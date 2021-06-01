import numpy as np
import itertools
from collections import Counter
from mantra_functions import (select_lineup, filter_players_without_vote,
                              add_roles, deploy_goalkeeper, mantra)
import db_functions as dbf
import time


def rec_cart(start: int, list_of_roles: list, partial: list, results: list,
             players_needed: int, scheme_used: str, some_counter: Counter,
             used_counters: list):

    # To avoid repeating calculations: if roles are the same the result is the
    # same no matter the players
    if Counter(partial) in used_counters:
        return

    # Define 2 conditions to filter
    cond1 = too_many_attackers(list_of_roles=partial)
    if some_counter:
        cond2 = option_is_not_compatible(field_counter=some_counter,
                                         option_counter=Counter(partial))
    else:
        cond2 = False

    if partial and (cond1 | cond2):
        return

    if len(partial) == len(list_of_roles):
        if enough_defenders(players_needed=players_needed,
                            list_of_roles=partial,
                            scheme_used=scheme_used):
            results.append(partial)
            used_counters.append(Counter(partial))
        return

    for element in list_of_roles[start]:
        rec_cart(start=start+1, list_of_roles=list_of_roles,
                 partial=partial+[element], results=results,
                 players_needed=players_needed, scheme_used=scheme_used,
                 some_counter=some_counter, used_counters=used_counters)


def roles2matrix(players_needed: int, list_of_roles: list, scheme_used: str,
                 field_counter: Counter) -> np.array:

    # Split strings into lists
    split = split_roles(list_of_roles=list_of_roles, by='/')

    # Create valid options
    perms = []
    rec_cart(start=0, list_of_roles=split, partial=[], results=perms,
             players_needed=players_needed, scheme_used=scheme_used,
             some_counter=field_counter, used_counters=[])

    # Map into ids
    roles2id = [RL_MAP[rl] for c in perms for rl in c]
    id_array = np.array(roles2id).reshape(-1, len(list_of_roles))
    return np.sort(id_array, axis=1)


def lineup_matrix_and_ntiles(players_needed: int, roles_in_lineup: list,
                             scheme_used: str,
                             field_counter: Counter) -> tuple:
    id_arr = roles2matrix(players_needed=players_needed,
                          list_of_roles=roles_in_lineup,
                          scheme_used=scheme_used,
                          field_counter=field_counter)
    return id_arr, id_arr.shape[0]


def adapt_roles(scheme_used: str, list_of_roles: list) -> list:

    original = split_roles(list_of_roles=list_of_roles, by='/')
    options_per_role = dict(dbf.db_select(table='malus',
                                          columns=['role', 'malus'],
                                          where=''))
    options_per_role = {k: v.split(';') for k, v in options_per_role.items()}

    special_schemes = ['4-1-4-1']
    if scheme_used not in special_schemes:
        options_per_role['T'] = options_per_role['T1']
        options_per_role['W'].remove('T1')
    else:
        options_per_role['T'] = options_per_role['T2']
        options_per_role['W'].remove('T')
        options_per_role['W'].remove('T1')
    del options_per_role['T1'], options_per_role['T2']
    adapted = []
    for i, el in enumerate(original):
        tmp = [options_per_role[rl] for rl in el]
        res = list(set([rl for ls in tmp for rl in ls]))
        adapted.append('/'.join(el+res))
    return adapted


def remove_attackers_from_scheme(roles_in_scheme: list, pc_in_field: int,
                                 a_in_field: int) -> tuple:

    # First remove Pc
    for _ in range(pc_in_field):
        try:
            roles_in_scheme.remove('A/Pc')
        except ValueError:
            pass

    # Then remove A: first look for A/Pc
    for _ in range(a_in_field):
        try:
            roles_in_scheme.remove('A/Pc')
            a_in_field -= 1
        except ValueError:
            pass

    # Pure A
    for _ in range(a_in_field):
        try:
            roles_in_scheme.remove('A')
            a_in_field -= 1
        except ValueError:
            pass

    # Finally W/A and T/A since they are never together
    if (a_in_field and
            a_in_field <= count_roles(['W/A', 'T/A'], roles_in_scheme)):
        a = [rl for rl in roles_in_scheme if 'A' in rl][:a_in_field]
        for rl in a:
            roles_in_scheme.remove(rl)
            a_in_field -= 1

    return a_in_field, roles_in_scheme

# def scheme_matrix_and_nrepeat(players_needed: int, scheme_used: str,
#                               field_counter: Counter, is_adapted=False,
#                               number_of_a=0, number_of_pc=0) -> tuple:
#
#     roles_in_scheme = dbf.db_select(
#             table='schemes_details',
#             columns=['details'],
#             where=f'scheme = "{scheme_used}"')[0].split(', ')[1:]
#
#     if is_adapted:
#         pc = [rl for rl in roles_in_scheme if 'Pc' in rl][:number_of_pc]
#         for rl in pc: roles_in_scheme.remove(rl)
#
#         if number_of_a >= count_roles(['A/Pc'], roles_in_scheme):
#             n = count_roles(['A/Pc'], roles_in_scheme)
#             for _ in range(n):
#                 roles_in_scheme.remove('A/Pc')
#                 number_of_a -= 1
#
#         if number_of_a and number_of_a <= count_roles(['A'], roles_in_scheme):
#             for _ in range(number_of_a):
#                 roles_in_scheme.remove('A')
#                 number_of_a = -1
#
#         # Since W/A and T/A are never together
#         if (number_of_a and
#                 number_of_a <= count_roles(['W/A', 'T/A'], roles_in_scheme)):
#             a = [rl for rl in roles_in_scheme if 'A' in rl][:number_of_a]
#             for rl in a:
#                 roles_in_scheme.remove(rl)
#                 number_of_a -= 1
#
#         if number_of_a:
#             # It means scheme is not valid
#             return np.array([]), 0
#
#         roles_in_scheme = adapt_roles(scheme_used=scheme_used,
#                                       list_of_roles=roles_in_scheme)
#
#     id_arr = roles2matrix(players_needed=players_needed,
#                           list_of_roles=roles_in_scheme,
#                           scheme_used=scheme_used,
#                           field_counter=field_counter)
#     return id_arr, id_arr.shape[0]


def scheme_matrix_and_nrepeat(players_needed: int, scheme_used: str,
                              field_counter: Counter, is_adapted: bool,
                              counting_malus: bool, number_of_a: int,
                              number_of_pc: int) -> tuple:

    roles_in_scheme = dbf.db_select(
            table='schemes_details',
            columns=['details'],
            where=f'scheme = "{scheme_used}"')[0].split(', ')[1:]

    if is_adapted:
        a_left, roles_in_scheme = remove_attackers_from_scheme(
                roles_in_scheme=roles_in_scheme, pc_in_field=number_of_pc,
                a_in_field=number_of_a)

        if a_left:
            # It means scheme is not valid
            return np.array([]), 0

        # When we count malus this adaptation must be skipped
        if not counting_malus:
            roles_in_scheme = adapt_roles(scheme_used=scheme_used,
                                          list_of_roles=roles_in_scheme)

    id_arr = roles2matrix(players_needed=players_needed,
                          list_of_roles=roles_in_scheme,
                          scheme_used=scheme_used,
                          field_counter=field_counter)
    return id_arr, id_arr.shape[0]


def optimal_solution(scheme_used: str, field_info: list,
                     bench_names_options: list, bench_roles_options: list,
                     players_needed: int) -> tuple:

    field_roles = [rl.replace(';', '/') for nm, rl in field_info]

    for n_comb, r_comb in zip(bench_names_options, bench_roles_options):
        tmp = field_roles + list(r_comb)
        if (too_many_attackers(list_of_roles=tmp) or
                not enough_defenders(players_needed=players_needed,
                                     list_of_roles=tmp,
                                     scheme_used=scheme_used)):
            continue

        fld_cnt = Counter([i for j in tmp for i in j.split('/')])
        if solution_exists(players_needed=players_needed,
                           scheme_used=scheme_used, roles_in_lineup=tmp,
                           field_counter=fld_cnt, is_adapted=False):
            return field_info + list(zip(n_comb, r_comb)), ''

    return [], ''


def efficient_solution(scheme_used: str, field_info: list,
                       bench_names_options: list, bench_roles_options: list,
                       players_needed: int) -> tuple:

    field_roles = [rl.replace(';', '/') for nm, rl in field_info]

    for n_comb, r_comb in zip(bench_names_options, bench_roles_options):
        tmp = field_roles + list(r_comb)
        if (too_many_attackers(list_of_roles=tmp) or
                not enough_defenders(players_needed=players_needed,
                                     list_of_roles=tmp,
                                     scheme_used='')):
            continue

        other_schemes = only_compatible_schemes(list_of_roles=tmp,
                                                players_needed=players_needed,
                                                scheme_to_exclude=scheme_used)

        fld_cnt = Counter([i for j in tmp for i in j.split('/')])
        for sch in other_schemes:
            if solution_exists(players_needed=players_needed,
                               scheme_used=sch, roles_in_lineup=tmp,
                               field_counter=fld_cnt, is_adapted=False):
                return field_info + list(zip(n_comb, r_comb)), sch

    return [], ''


def solution_exists(players_needed: int, scheme_used: str,
                    roles_in_lineup: list, field_counter: Counter,
                    is_adapted: bool, number_of_a=0, number_of_pc=0):

    lineup_mtx, n_tiles = lineup_matrix_and_ntiles(
            players_needed=players_needed, roles_in_lineup=roles_in_lineup,
            scheme_used=scheme_used, field_counter=field_counter)

    scheme_mtx, n_repeat = scheme_matrix_and_nrepeat(
            players_needed=players_needed, scheme_used=scheme_used,
            field_counter=field_counter, is_adapted=is_adapted,
            counting_malus=False, number_of_a=number_of_a,
            number_of_pc=number_of_pc)

    # This check is only needed for adapted solutions
    if is_adapted and not scheme_mtx.sum():
        return np.array([]), np.array([])

    lineup_mtx_full = np.repeat(lineup_mtx, n_repeat, axis=0)
    scheme_mtx_full = np.tile(scheme_mtx, (n_tiles, 1))

    all_res = (lineup_mtx_full == scheme_mtx_full).all(axis=1)

    if not is_adapted:
        return all_res.any()

    return ((lineup_mtx_full, all_res) if all_res.any() else
            (np.array([]), np.array([])))


def count_roles(which_roles: list, list_of_roles: list) -> int:
    res = 0
    for rl in which_roles:
        res += sum([1 for i in list_of_roles if rl == i])
    return res


def split_roles(list_of_roles: list, by: str) -> list:
    return [rl.split(by) for rl in list_of_roles]


def n_defenders(list_of_roles: list) -> int:
    return sum([1 for rl in list_of_roles if
                {'Dc', 'Dd', 'Ds'} & set(rl.split('/'))])


def min_n_defenders(players_needed: int, scheme_used: str) -> int:

    missing_players = 10 - players_needed

    # When no scheme is passed it means a general check: there is always a
    # min number of defenders needed, indipendently from the scheme. In normal
    # conditions this number is 3 because no schemes accept less than 3
    # defenders. When playing with less than 11 players, it depends on how many
    # players are missing
    if not scheme_used:
        return 3 - missing_players

    # On the other hand, when scheme is specified it means min number of
    # defenders must be at least equal to those needed by the scheme taking
    # into account the number of players playing.
    def_in_scheme = int(scheme_used[0])
    return def_in_scheme - missing_players


def enough_defenders(players_needed: int, list_of_roles: list,
                     scheme_used: str) -> bool:

    def_in_lineup = n_defenders(list_of_roles=list_of_roles)
    min_def = min_n_defenders(players_needed=players_needed,
                              scheme_used=scheme_used)
    return True if def_in_lineup >= min_def else False


def too_many_attackers(list_of_roles: list) -> bool:

    # It is not possible to play with 3 Pc
    pc_count = sum([1 for i in list_of_roles if i == 'Pc'])
    cond1 = pc_count == 3

    # It is not possible to play with 2 Pc + A
    a_count = sum([1 for i in list_of_roles if i == 'A'])
    cond2 = pc_count == 2 and a_count > 0

    # It is not possible to play with 2 Pc + >1 T
    t_count = sum([1 for i in list_of_roles if i == 'T'])
    ta_count = sum([1 for i in list_of_roles if i == 'T/A'])
    cond3 = pc_count == 2 and (t_count + ta_count) > 1

    # It is not possible to play with 1 Pc + >2 A
    cond4 = pc_count + a_count > 3

    return True if (cond1 | cond2 | cond3 | cond4) else False


def option_is_not_compatible(field_counter: Counter,
                             option_counter: Counter) -> bool:

    # To be compatible, option_counter must contain ALL the roles in field
    return True if option_counter - field_counter else False


def only_compatible_schemes(list_of_roles: list, players_needed: int,
                            scheme_to_exclude) -> list:

    all_schemes = dbf.db_select(table='schemes_details',
                                columns=['scheme'],
                                where=f'scheme != "{scheme_to_exclude}"')

    # First of all we need to remove all those schemes whose number of
    # defenders is not compatible with the roles in field
    all_schemes = [sch for sch in all_schemes if enough_defenders(
            players_needed=players_needed, list_of_roles=list_of_roles,
            scheme_used=sch)]

    # Then we do the same considering the number of attackers
    res = []
    n_pc = count_roles(['Pc'], list_of_roles)
    for sch in all_schemes:
        rl_in_scheme = dbf.db_select(
                table='schemes_details',
                columns=['details'],
                where=f'scheme = "{sch}"')[0].split(', ')[1:]

        # To be a compatible scheme it must at least equal the number of
        # attackers playing
        if count_roles(['A/Pc'], rl_in_scheme) >= n_pc:
            res.append(sch)
    return res


def adapted_solution(field_info: list, bench_names_options: list,
                     bench_roles_options: list, players_needed: int) -> tuple:

    field_roles = [rl.replace(';', '/') for _, rl in field_info]

    already_tried = []
    results = []
    for n_comb, r_comb in zip(bench_names_options, bench_roles_options):
        if r_comb in already_tried:
            continue
        already_tried.append(r_comb)
        tmp = field_roles + list(r_comb)
        if (too_many_attackers(list_of_roles=tmp) or
                not enough_defenders(players_needed=players_needed,
                                     list_of_roles=tmp, scheme_used='')):
            continue

        all_schemes = only_compatible_schemes(list_of_roles=tmp,
                                              players_needed=players_needed,
                                              scheme_to_exclude='')
        n_pc = count_roles(['Pc'], tmp)
        n_a = count_roles(['A'], tmp)
        tmp = [rl for rl in tmp if rl not in ['A', 'Pc']]
        fld_cnt = Counter([i for j in tmp for i in j.split('/')])
        for sch in all_schemes:

            lineup_mtx_full, all_res = solution_exists(
                    players_needed=players_needed, scheme_used=sch,
                    roles_in_lineup=tmp, field_counter=fld_cnt,
                    is_adapted=True, number_of_a=n_a, number_of_pc=n_pc)

            if lineup_mtx_full.sum():
                good_lineups = lineup_mtx_full[all_res]
                good_lineups = [Counter(i) for i in good_lineups]

                id_arr, _ = scheme_matrix_and_nrepeat(
                        players_needed=players_needed, scheme_used=sch,
                        field_counter=Counter([]), is_adapted=True,
                        counting_malus=True, number_of_a=n_a,
                        number_of_pc=n_pc)

                id_arr = [Counter(i) for i in id_arr]
                for c1, c2 in itertools.product(good_lineups, id_arr):
                    n_malus = sum((c1-c2).values())

                    if n_malus == 1:
                        return field_info + list(
                            zip(n_comb, r_comb)), sch, n_malus
                    results.append((field_info + list(zip(n_comb, r_comb)),
                                    sch,
                                    n_malus))

    if not results:
        return [], '', 0

    results.sort(key=lambda x: x[2])
    return results[0]


RL_MAP = {'Dc': 1, 'Dd': 2, 'Ds': 3, 'E': 4, 'M': 5, 'C': 6,
          'W': 7, 'T': 8, 'A': 9, 'Pc': 10}

#  1, FC BOMBAGALLO, HERNANI+PALOMINO+FARAGO, 1
#  1, FC 104, DANILO, 1
#  2, FC 104, SCHIATTARELLA+DANILO, 1
#  7, Ciolle United, BAKA+DEMIRAL, 1
#  7, Bucalina, IONITA+ALVES+MASIELLO, 1
# 13, F C Happy Milf, CALABRIA, 1
# 15, F C Happy Milf, STRYGER LARSEN, 1
# 23, Bucalina, MASIELLO, 1
# 26, Fc Roxy, MIKI+MIRANCHUK+DANILO, 3
# 26, Bucalina, PEREYRA+CANDREVA, 1,                  gioca in 10
# 31, F C Happy Milf, zielinski+mandragora+di lorenzo, 4

# 4, Bucalina efficiente
# 7, FC BOMBAGALLO efficiente
# 8, FC BOMBAGALLO efficiente
# 14, F C Happy Milf efficiente
DAY = 13
TEAM = 'F C Happy Milf'

scheme = dbf.db_select(
            table='schemes',
            columns=[f'day_{DAY}'],
            where=f'team_name = "{TEAM}"')[0]

field, bench = select_lineup(DAY, TEAM)

# Keep only players with vote
field_with_vote = filter_players_without_vote(DAY, field)
bench_with_vote = filter_players_without_vote(DAY, bench)

# Extract goal-keepers from field and bench
gkeep_field, field_with_roles = add_roles(field_with_vote)
gkeep_bench, bench_with_roles = add_roles(bench_with_vote)

# Define the goal-keeper to use and the max number of substitutions allowed
gkeep, max_subst = deploy_goalkeeper(gkeep_field, gkeep_bench)

# Actual number of substitutions
n_subst = min(max_subst, 10 - len(field_with_roles))
complete_lineup, new_scheme = [], ''

# OLD version
# a = mantra(DAY, TEAM, 10, True, save_lineup=False)

t0 = time.time()
if not n_subst:
    complete_lineup, new_scheme = [gkeep] + field_with_roles, ''
else:
    bench_names = [nm for nm, rl in bench_with_roles]
    bench_names_comb = list(itertools.combinations(bench_names, n_subst))
    bench_roles = [rl.replace(';', '/') for nm, rl in bench_with_roles]
    bench_roles_comb = list(itertools.combinations(bench_roles, n_subst))

    complete_lineup, new_scheme = optimal_solution(
            scheme_used=scheme,
            field_info=field_with_roles,
            bench_names_options=bench_names_comb,
            bench_roles_options=bench_roles_comb,
            players_needed=10)

    if not complete_lineup:
        complete_lineup, new_scheme = efficient_solution(
                scheme_used=scheme,
                field_info=field_with_roles,
                bench_names_options=bench_names_comb,
                bench_roles_options=bench_roles_comb,
                players_needed=10)

    if not complete_lineup:
        complete_lineup, new_scheme, malus = adapted_solution(
                    field_info=field_with_roles,
                    bench_names_options=bench_names_comb,
                    bench_roles_options=bench_roles_comb,
                    players_needed=10)

    complete_lineup = [gkeep] + complete_lineup
print(time.time() - t0)
print(complete_lineup)
print(new_scheme)
print(malus)
