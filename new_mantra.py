import numpy as np
import itertools
from mantra_functions import (select_lineup, filter_players_without_vote,
                              add_roles, deploy_goalkeeper)
import db_functions as dbf
import time


def roles2matrix(list_of_roles):
    split = [i.split('/') for i in list_of_roles]
    all_combs = list(itertools.product(*split))
    all_combs = [i for i in all_combs if not invalid_lineup(i)]
    all_combs = [RL_MAP[rl] for c in all_combs for rl in c]
    return np.array(all_combs).reshape(-1, len(list_of_roles))


def lineup_matrix_and_ntiles(roles_in_lineup):
    mtx = np.sort(roles2matrix(roles_in_lineup), axis=1)
    return mtx, mtx.shape[0]


def adapt_roles(scheme_used, list_of_roles):

    original = [rl.split('/') for rl in list_of_roles]
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
        # if len(el) == 1:
        #     # adapted.append(el[0])
        #     res = options_per_role[el[0]]
        # else:
        tmp = [options_per_role[rl] for rl in el]
        res = list(set([rl for ls in tmp for rl in ls]))
        adapted.append('/'.join(el+res))
    return adapted


def convert_t(scheme_used, list_of_roles):
    special_schemes = ['4-1-4-1']
    return ([rl.replace('T', 'T1') for rl in list_of_roles] if
            scheme_used in special_schemes else
            [rl.replace('T', 'T2') for rl in list_of_roles])


def scheme_matrix_and_nrepeat(scheme_used, is_adapted=False,
                              number_of_a=0, number_of_pc=0):
    roles_in_scheme = dbf.db_select(
            table='schemes_details',
            columns=['details'],
            where=f'scheme = "{scheme_used}"')[0].split(', ')[1:]

    if is_adapted:
        pc = [rl for rl in roles_in_scheme if 'Pc' in rl][:-number_of_pc]
        for rl in pc: roles_in_scheme.remove(rl)

        if count_role('A', roles_in_scheme) == number_of_a:
            a = [rl for rl in roles_in_scheme if 'A' in rl]
            for rl in a: roles_in_scheme.remove(rl)
        # others = [rl for rl in roles_in_scheme if rl not in a and rl not in pc]
        # roles_in_scheme = others + a[:-number_of_a] + pc
        roles_in_scheme = adapt_roles(scheme_used=scheme_used,
                                      list_of_roles=roles_in_scheme)

    mtx = np.sort(roles2matrix(roles_in_scheme), axis=1)
    return mtx, mtx.shape[0]


def optimal_solution(scheme_used, field_info,
                     bench_names_options, bench_roles_options):
    field_roles = [rl.replace(';', '/') for nm, rl in field_info]

    for n_comb, r_comb in zip(bench_names_options, bench_roles_options):
        tmp = field_roles + list(r_comb)
        lineup_mtx, n_tiles = lineup_matrix_and_ntiles(roles_in_lineup=tmp)
        scheme_mtx, n_repeat = scheme_matrix_and_nrepeat(
                scheme_used=scheme_used)

        lineup_mtx_full = np.repeat(lineup_mtx, n_repeat, axis=0)
        scheme_mtx_full = np.tile(scheme_mtx, (n_tiles, 1))

        all_res = (lineup_mtx_full == scheme_mtx_full).all(axis=1)
        if all_res.any():
            return field_info + list(zip(n_comb, r_comb))

    return []


def efficient_solution(scheme_used, field_info,
                       bench_names_options, bench_roles_options):
    field_roles = [rl.replace(';', '/') for nm, rl in field_info]

    other_schemes = dbf.db_select(
            table='schemes_details',
            columns=['scheme'],
            where=f'scheme != "{scheme_used}"')

    for n_comb, r_comb in zip(bench_names_options, bench_roles_options):
        tmp = field_roles + list(r_comb)
        lineup_mtx, n_tiles = lineup_matrix_and_ntiles(roles_in_lineup=tmp)

        for sch in other_schemes:
            scheme_mtx, n_repeat = scheme_matrix_and_nrepeat(scheme_used=sch)

            lineup_mtx_full = np.repeat(lineup_mtx, n_repeat, axis=0)
            scheme_mtx_full = np.tile(scheme_mtx, (n_tiles, 1))

            all_res = (lineup_mtx_full == scheme_mtx_full).all(axis=1)
            if all_res.any():
                return field_info + list(zip(n_comb, r_comb)), sch

    return [], ''


def count_role(which_role, list_of_roles, strict_equal=False):
    if strict_equal:
        return sum([1 for rl in list_of_roles if which_role == rl])
    else:
        return sum([1 for rl in list_of_roles if which_role in rl])


def invalid_lineup(list_of_roles):
    pc_count = sum([1 for i in list_of_roles if i == 'Pc'])
    a_count = sum([1 for i in list_of_roles if i == 'A'])

    cond1 = pc_count == 2 and a_count > 0
    cond2 = pc_count == 3
    cond3 = pc_count + a_count > 3
    return True if (cond1 | cond2 | cond3) else False


def only_schemes_compatible_with_n_pc(number_of_pc):
    res = []
    all_schemes = dbf.db_select(table='schemes_details',
                                columns=['scheme'],
                                where='')
    all_schemes = ['3-4-1-2']

    for sch in all_schemes:
        rl_in_scheme = dbf.db_select(
                table='schemes_details',
                columns=['details'],
                where=f'scheme = "{sch}"')[0].split(', ')[1:]
        if count_role('Pc', rl_in_scheme) >= number_of_pc:
            res.append(sch)
    return res


def adapted_solution(field_info, bench_names_options, bench_roles_options):
    field_roles = [rl.replace(';', '/') for nm, rl in field_info]
    n_pc = count_role('Pc', field_roles)
    n_a = count_role('A', field_roles, strict_equal=True)

    all_schemes = only_schemes_compatible_with_n_pc(n_pc)
    # all_schemes = ['3-5-1-1']

    for n_comb, r_comb in zip(bench_names_options, bench_roles_options):
        # if ('ZIELINSKI', 'MANDRAGORA', 'DI LORENZO') != n_comb:
        #     continue
        tmp = field_roles + list(r_comb)
        if invalid_lineup(tmp):
            continue

        # tmp = [rl for rl in tmp if rl != 'Pc']
        tmp = [rl for rl in tmp if rl not in ['A', 'Pc']]
        lineup_mtx, n_tiles = lineup_matrix_and_ntiles(roles_in_lineup=tmp)
        for sch in all_schemes:
            scheme_mtx, n_repeat = scheme_matrix_and_nrepeat(scheme_used=sch,
                                                             is_adapted=True,
                                                             number_of_a=n_a,
                                                             number_of_pc=n_pc)

            lineup_mtx_full = np.repeat(lineup_mtx, n_repeat, axis=0)
            scheme_mtx_full = np.tile(scheme_mtx, (n_tiles, 1))

            all_res = (lineup_mtx_full == scheme_mtx_full).all(axis=1)
            if all_res.any():
                return field_info + list(zip(n_comb, r_comb)), sch

    return [], ''


RL_MAP = {'Dc': 1, 'Dd': 2, 'Ds': 3, 'E': 4, 'M': 5, 'C': 6,
          'W': 7, 'T': 8, 'A': 9, 'Pc': 10}

DAY = 31
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

bench_names = [nm for nm, rl in bench_with_roles]
bench_names_comb = list(itertools.combinations(bench_names, n_subst))
bench_roles = [rl.replace(';', '/') for nm, rl in bench_with_roles]
bench_roles_comb = list(itertools.combinations(bench_roles, n_subst))

complete_lineup = optimal_solution(scheme_used=scheme,
                                   field_info=field_with_roles,
                                   bench_names_options=bench_names_comb,
                                   bench_roles_options=bench_roles_comb)
t0 = time.time()
if not complete_lineup:
    complete_lineup, new_scheme = efficient_solution(
            scheme_used=scheme,
            field_info=field_with_roles,
            bench_names_options=bench_names_comb,
            bench_roles_options=bench_roles_comb)

if not complete_lineup:
    complete_lineup, new_scheme = adapted_solution(
            field_info=field_with_roles,
            bench_names_options=bench_names_comb,
            bench_roles_options=bench_roles_comb)
print(t0 - time.time())
print(complete_lineup, new_scheme)

