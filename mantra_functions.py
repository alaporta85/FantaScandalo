import db_functions as dbf
from itertools import combinations, permutations
from collections import Counter


def add_roles(list_of_players):

	"""
	Add the corresponding role for each player in list_of_players. Ex:

	:param list_of_players: list, Ex. ['SKORUPSKI', 'ASAMOAH', ...]

	:return: tuple, Ex. [('SKORUPSKI', 'Por'), ('ASAMOAH', 'Ds;E'), ...]

	"""

	gkeep_list = []
	field_list = []
	for player in list_of_players:
		role = dbf.db_select(
				table='roles',
				columns=['role'],
				where=f'name = "{player}"')[0]

		if role == 'Por':
			gkeep_list.append((player, role))
		else:
			field_list.append((player, role))

	return gkeep_list, field_list


def check_when_0_subst(day, fantateam, players_in_field):

	"""
	Check if malus are assigned when all players in field have vote. This is
	possible because it is allowed to deploy from the beginning a lineup with
	malus.

	:param day: int
	:param fantateam: str
	:param players_in_field: list, Ex. [('CAPUANO', 'Ds;Dc'), ...]

	:return: tuple, Ex. (0, '3-4-3')

	"""

	malus = 0

	scheme = dbf.db_select(
			table='schemes',
			columns=[f'day_{day}'],
			where=f'team_name = "{fantateam}"')[0]

	scheme_details = dbf.db_select(
			table='schemes_details',
			columns=['details'],
			where=f'scheme = "{scheme}"')[0].split(', ')[1:]

	for i in range(len(players_in_field)):
		role_to_cover = scheme_details[i].split('/')
		role_in_field = players_in_field[i][1].split(';')

		rl = set(role_to_cover) & set(role_in_field)

		# If player can cover the position with no malus, one of the valid
		# roles will be assigned
		if rl:
			players_in_field[i] = (players_in_field[i][0], list(rl)[0])

		# else, a role with malus
		else:
			malus += 1
			rl_malus = dbf.db_select(
					table='malus',
					columns=['malus'],
					where=f'role = "{role_to_cover[0]}"')[0]
			rl_malus = rl_malus.split(';')
			rl = set(rl_malus) & set(role_in_field)
			players_in_field[i] = (players_in_field[i][0], f'*{list(rl)[0]}')

	return malus, scheme


def convert_t(scheme, roles, mode):

	"""
	Convert T into T1 or T2 according to the module used or viceversa
	(T1, T2 into T) depending on the 'mode' parameter.

	T has special rules for substitutions depending on the module used.
	Mode will be 'forward' at the beginning when looking for the valid lineup
	and 'back' when found.

	:param scheme: str, Ex. '3-5-2'
	:param roles: list, Ex. ['Dc', 'Dc', 'Pc', 'W', 'C', 'Dd', 'E', 'C', 'T']
	:param mode: str, 'back' or 'forward'

	:return: list, Ex. ['Dc', 'Dc', 'Pc', 'W2', 'C', 'Dd', 'E', 'C', 'T']

	"""

	if mode == 'back':
		roles = ['T' if (el == 'T1' or el == 'T1*' or
		                 el == 'T2' or el == 'T2*') else el for el in roles]
		return roles

	elif mode == 'forward':
		special_group = ['4-1-4-1']

		if scheme in special_group:
			return ['T2' if el == 'T' else el for el in roles]
		else:
			return ['T1' if el == 'T' else el for el in roles]


def create_players_candidates(list_of_tuples, players_needed):

	"""
	Create all the combinations of the players inside 'list_of_tuples'
	considering their roles. At the end each player will be single role. Ex:

		list_of_tuples = [(PERIN, 'Por'), (SKRINIAR, 'Dc'), (RADU, 'Dc, Dd')]

		candidates = [
					  [(PERIN, 'Por'), (SKRINIAR, 'Dc'), (RADU, 'Dc')],
					  [(PERIN, 'Por'), (SKRINIAR, 'Dc'), (RADU, 'Dd')]
					 ]

	:param list_of_tuples: list of tuples
	:param players_needed: int, number of players to deploy

	:return: list of lists

	"""

	# First separate players with just one role and players with more
	single = []
	multi = []

	for player, roles in list_of_tuples:

		if len(roles.split(';')) == 1:
			single.append((player, roles))
		else:
			# For each role of the player there will be a tuple inside 'multi'
			for role in roles.split(';'):
				multi.append((player, role))

	# Define how many players from 'multi' have to be added to 'single'
	players_to_add = players_needed - len(single)

	# Create the combinations and remove those where one or more players are
	# repeated
	multi = combinations(multi, players_to_add)
	multi = [el for el in multi if
	         len(set([i[0] for i in el])) == players_to_add]

	# Create all the candidates where each player is single role
	candidates = []
	for comb in multi:
		candidates.append(single + [pl for pl in comb])

	return candidates


def create_schemes_candidates(roles, players_needed):

	"""
	See function create_players_candidates.

	:param roles: list of strings
	:param players_needed: int

	:return: list of lists

	"""

	def comb_is_valid(comb):

		"""
		Check that no interchangeble roles are present in comb.

		:param comb: tuple

		:return: bool

		"""

		return len(set([idx for idx, _ in comb])) == players_needed

	# Roles which are interchangeble will have the same index
	single = [(i, rl) for i, rls in enumerate(roles) for rl in rls.split('/')]
	combs = list(combinations(single, players_needed))

	return [[rl for _, rl in comb] for comb in combs if comb_is_valid(comb)]


def filter_players_without_vote(day, players):

	"""
	Return the list players after removing the ones without vote on that day.

	:param day: int
	:param players: list of str

	:return: list of str

	"""

	return [pl for pl in players if player_vote(day, pl) != 'sv']


def flatten_dict(counter_dict):

	"""
	Flatten the dict containing the roles' counts into a list.

	:param counter_dict: Counter, Ex. Counter({'M': 2, 'A': 2, 'Dc': 1})

	:return: list, Ex. ['Dc', 'M', 'M', 'A', 'A']

	"""

	return [role for role in counter_dict for _ in range(counter_dict[role])]


def deploy_goalkeeper(gkeep_field, gkeep_bench):

	"""
	Manage the goal-keeper substitution, which is always the first one to do,
	and define the number of max substitutions allowed.

	:param gkeep_field: list, Ex. [('HANDANOVIC', 'Por')]
	:param gkeep_bench: list, Ex. [('PADELLI', 'Por')]

	:return: tuple, Ex. (('HANDANOVIC', 'Por'), 3)

	"""

	if gkeep_field:
		gkeep = gkeep_field[0]
		max_subst = 3

	elif not gkeep_field and gkeep_bench:
		gkeep = gkeep_bench[0]
		max_subst = 2

	else:
		gkeep = None
		max_subst = 3

	return gkeep, max_subst


def mantra(day, fantateam, starting_players, roles, save_lineup=True):

	"""
	Find the valid lineup of the day.

	:param day: int
	:param fantateam: str
	:param starting_players: int
	:param roles: bool, if False return only the names of the players
	:param save_lineup: bool

	:return: tuple, (lineup, scheme, n_malus)

	"""

	# Separate field and bench
	field, bench = select_lineup(day, fantateam)

	# Keep only players with vote
	field_with_vote = filter_players_without_vote(day, field)
	bench_with_vote = filter_players_without_vote(day, bench)

	# Extract goal-keepers from field and bench
	gkeep_field, field_with_roles = add_roles(field_with_vote)
	gkeep_bench, bench_with_roles = add_roles(bench_with_vote)

	# Define the goal-keeper to use and the max number of substitutions allowed
	gkeep, max_subst = deploy_goalkeeper(gkeep_field, gkeep_bench)

	# Actual number of substitutions
	n_subst = min(max_subst, starting_players - len(field_with_roles))

	# If no substitutions needed
	if not n_subst:
		n_malus, scheme = check_when_0_subst(day, fantateam, field_with_roles)

		if gkeep:
			field_with_roles.insert(0, gkeep)

		if save_lineup:
			save_mantra_lineup(day, fantateam, field_with_roles)

		if roles:
			return field_with_roles, scheme, n_malus
		else:
			return [pl for pl, rl in field_with_roles], scheme, n_malus

	# Number of players allowed in the final lineup
	players_allowed = len(field_with_roles) + n_subst

	# All the schemes
	scheme, other_schemes = schemes_to_iterate(day, fantateam)

	# Remove some role from bench, to speed everything up
	bench_with_roles = filter_for_pc(field_with_roles, bench_with_roles)

	# Look for an optimal solution
	result, new_scheme = optimal(scheme, field_with_roles,
	                             bench_with_roles, n_subst, players_allowed)
	if result:

		if gkeep:
			result.insert(0, gkeep)

		if save_lineup:
			save_mantra_lineup(day, fantateam, result)

		if roles:
			return result, new_scheme, 0
		else:
			return [pl for pl, rl in result], new_scheme, 0

	# In case no optimal solution is found, look for a solution with malus
	result, new_scheme = adapted(other_schemes, field_with_roles,
	                             bench_with_roles, n_subst, players_allowed)

	if result:
		n_malus = sum([1 for nm, rl in result if '*' in rl])

		if gkeep:
			result.insert(0, gkeep)

		if save_lineup:
			save_mantra_lineup(day, fantateam, result)

		if roles:
			return result, new_scheme, n_malus
		else:
			return [pl for pl, rl in result], new_scheme, n_malus

	# In case no adapted solution is found, repeat with less players
	return mantra(day, fantateam, starting_players-1, roles, save_lineup)


def player_vote(day, player_name):

	"""
	Return player's vote of the day.

	:param day: int
	:param player_name: str
	:return:

	"""

	vote = dbf.db_select(
		    table='votes',
            columns=['alvin'],
            where=f'day={day} AND name="{player_name}"')

	return vote[0] if vote else 'sv'


def schemes_to_iterate(day, fantateam):

	"""
	Return the scheme chosen by the player and the others.

	:param day: int
	:param fantateam: str

	:return: tuple, Ex. ('3-4-1-2', ['3-4-3', '3-4-2-1', '3-5-2',...])

	"""

	scheme = dbf.db_select(
			table='schemes',
			columns=[f'day_{day}'],
			where=f'team_name = "{fantateam}"')[0]

	all_schemes = dbf.db_select(
			table='schemes_details',
			columns=['scheme'])

	return scheme, all_schemes


def select_lineup(day, fantateam):

	"""
	Return 2 lists: the first 11 players and the bench.
	Only the names, no roles.

	:param day: int
	:param fantateam: str

	:return: tuple, Ex. (['HANDANOVIC', 'MAGNANI', 'SKRINIAR', 'MIRANDA', ...],
						 ['MANDZUKIC', 'PAVOLETTI', 'ZIELINSKI', ...])

	"""

	lineup = dbf.db_select(
			table='lineups',
			columns=[f'day_{day}'],
			where=f'team_name = "{fantateam}"')[0].split(', ')

	field = lineup[:11]
	bench = lineup[11:]

	return field, bench


def filter_for_pc(players_in_field, subst):

	"""
	Remove players from the bench, when possible, to make the process faster.
	If 2 Pc or 2 A + 1 Pc are already in the field, no more A or Pc are allowed
	and so they are removed from the bench, if present.

	:param players_in_field: list, Ex. [('MAGNANI', 'Dc'), ...]
	:param subst: list, [('MANDZUKIC', 'Pc'), ('ZIELINSKI', 'C;T'), ...)]

	:return: LIST, EX. [('ZIELINSKI', 'C;T'), ...)]

	"""

	pc_already_in_field = sum([1 for _, rl in players_in_field if rl == 'Pc'])
	a_already_in_field = sum([1 for _, rl in players_in_field if rl == 'A'])

	cond1 = pc_already_in_field == 2
	cond2 = pc_already_in_field == 1 and a_already_in_field == 2

	if cond1 or cond2:
		subst = [el for el in subst if el[1] != 'Pc']
		subst = [(nm, rl.replace(';A', '')) for nm, rl in subst if rl != 'A']

	return subst


def optimal(scheme, field_with_roles, bench_with_roles,
            n_substitutions, n_players):

	"""
	Look for an optimal solution.

	:param scheme: str, Ex. '4-3-3'
	:param field_with_roles: list, Ex. [('ASAMOAH', 'Ds;E'), ...]
	:param bench_with_roles: list, Ex. [('DE ROON', 'M;C'), ...]
	:param n_substitutions: int
	:param n_players: int, players to deploy


	:return: tuple, (lineup, scheme) if found else (None, None)

	"""

	# Create all the combinations from bench
	substitutes = list(combinations(bench_with_roles, n_substitutions))

	# Extract the roles allowed in the scheme and create the combinations
	scheme_details = dbf.db_select(
			table='schemes_details',
			columns=['details'],
			where=f'scheme = "{scheme}"')[0].split(', ')[1:]

	schemes_candidates = create_schemes_candidates(scheme_details, n_players)

	# Iterate over each possible group of substitutes
	for bench_pos, option in enumerate(substitutes):

		# Add it to the players with vote
		final_field = field_with_roles + list(option)
		if too_many_pc(final_field):
			continue

		# Create all the lineups combinations
		players_candidates = create_players_candidates(final_field,
		                                               n_players)

		# Each lineup is checked with each possible combination of roles
		# defined above
		for lineup in players_candidates:

			lineup_names = [el[0] for el in lineup]
			lineup_roles = convert_t(scheme, [el[1] for el in lineup],
			                         mode='forward')

			# Filter the options
			filtered_sch_cand = filter_schemes_candidates(lineup_roles,
			                                              schemes_candidates)
			for candidate in filtered_sch_cand:

				# Transform wings
				candidate = convert_t(scheme, candidate, mode='forward')

				# Roles which are not covered by this lineup combination
				uncovered = Counter(candidate) - Counter(lineup_roles)
				uncovered = flatten_dict(uncovered)

				# If all roles are covered, solution is found
				if not uncovered:
					# Transform wings back
					lineup_roles = convert_t(scheme, lineup_roles,
					                         mode='back')
					return list(zip(lineup_names, lineup_roles)), scheme

	return None, None


def filter_schemes_candidates(lineup_roles, schemes_cand):

	"""
	Similar to filter_for_pc but for the schemes candidates.

	:param lineup_roles: list
	:param schemes_cand: list

	:return: list

	"""

	n_pc = sum([1 for rl in lineup_roles if rl == 'Pc'])
	n_a = sum([1 for rl in lineup_roles if rl == 'A'])

	filtered = [el for el in schemes_cand if
	            sum([1 for rl in el if rl == 'Pc']) >= n_pc]
	filtered = [el for el in filtered if
	            sum([1 for rl in el if rl == 'A']) >= n_a]

	return filtered


def efficient(list_of_schemes, field_with_roles, bench_with_roles,
              n_substitutions, n_players):

	"""
	Look for an efficient solution.

	:param list_of_schemes: list, Ex. ['4-3-3', '3-4-3', '3-4-1-2', ...]
	:param field_with_roles: list, Ex. [('ASAMOAH', 'Ds;E'), ...]
	:param bench_with_roles: list, Ex. [('DE ROON', 'M;C'), ...]
	:param n_substitutions: int
	:param n_players: int, players to deploy


	:return: tuple, (lineup, scheme) if found else (None, None)

	"""

	# Create all the combinations from bench
	substitutes = list(combinations(bench_with_roles, n_substitutions))

	# Iterate over each possible group of substitutes
	for bench_pos, option in enumerate(substitutes):

		# Add it to the players with vote
		final_field = field_with_roles + list(option)
		if too_many_pc(final_field):
			continue

		# Create all the lineups combinations
		players_candidates = create_players_candidates(final_field, n_players)

		# Iterate over the schemes
		for scheme in list_of_schemes:
			# Extract the roles allowed in the scheme and create the
			# combinations
			scheme_details = dbf.db_select(
					table='schemes_details',
					columns=['details'],
					where=f'scheme = "{scheme}"')[0].split(', ')[1:]

			schemes_candidates = create_schemes_candidates(scheme_details,
			                                               n_players)

			# Each lineup is checked with each possible combination of roles
			# defined above
			for lineup in players_candidates:

				lineup_names = [el[0] for el in lineup]
				lineup_roles = convert_t(scheme, [el[1] for el in lineup],
				                         mode='forward')
				filtered_sch_cand = filter_schemes_candidates(lineup_roles,
				                                              schemes_candidates)
				for candidate in filtered_sch_cand:

					# Transform wings
					candidate = convert_t(scheme, candidate, mode='forward')

					# Roles which are not covered by this lineup combination
					uncovered = Counter(candidate) - Counter(lineup_roles)
					uncovered = flatten_dict(uncovered)

					# If all roles are covered, solution is found
					if not uncovered:
						# Transform wings back
						lineup_roles = convert_t(scheme, lineup_roles,
						                         mode='back')
						return list(zip(lineup_names, lineup_roles)), scheme

	return None, None


def adapted(list_of_schemes, field_with_roles, bench_with_roles,
            n_substitutions, n_players):

	"""
	Look for an adapted solution.

	:param list_of_schemes: list, Ex. ['4-3-3', '3-4-3', '3-4-1-2', ...]
	:param field_with_roles: list, Ex. [('ASAMOAH', 'Ds;E'), ...]
	:param bench_with_roles: list, Ex. [('DE ROON', 'M;C'), ...]
	:param n_substitutions: int
	:param n_players: int, players to deploy


	:return: tuple, (lineup, scheme) if found else (None, None)

	"""

	best_lineup = None
	best_scheme = None
	n_malus = 11          # Initialize number of malus

	# Create all the combinations from bench
	substitutes = list(combinations(bench_with_roles, n_substitutions))

	# Iterate over each possible group of substitutes
	for bench_pos, option in enumerate(substitutes):

		# Add it to the players with vote
		final_field = field_with_roles + list(option)
		if too_many_pc(final_field):
			continue

		# Create all the lineups combinations
		players_candidates = create_players_candidates(final_field,
		                                               n_players)
		# Iterate over the schemes
		for scheme in list_of_schemes:

			# Extract the roles allowed in the scheme and create the combinations
			scheme_details = dbf.db_select(
					table='schemes_details',
					columns=['details'],
					where=f'scheme = "{scheme}"')[0].split(', ')[1:]

			schemes_candidates = create_schemes_candidates(scheme_details,
			                                               n_players)

			# Each lineup is checked with each possible combination of roles
			# defined above
			for lineup in players_candidates:

				lineup_names = [el[0] for el in lineup]
				lineup_roles = convert_t(scheme, [el[1] for el in lineup],
				                         mode='forward')
				filtered_sch_cand = filter_schemes_candidates(lineup_roles,
				                                              schemes_candidates)
				for candidate in filtered_sch_cand:

					# Transform wings
					candidate = convert_t(scheme, candidate, mode='forward')

					# Roles which are not covered by this lineup combination
					uncovered = Counter(candidate) - Counter(lineup_roles)
					uncovered = flatten_dict(uncovered)

					# If all roles are covered, solution is found
					if not uncovered:
						# Transform wings back
						lineup_roles = convert_t(scheme, lineup_roles,
						                         mode='back')
						return list(zip(lineup_names, lineup_roles)), scheme
					# else, check if it is possible to find an adapted
					# solution
					elif (len(uncovered) < n_malus and
					      len(uncovered) <= n_substitutions):

						# Roles not used in field
						available = Counter(lineup_roles) - Counter(candidate)
						available = flatten_dict(available)

						# Permutations of the uncovered roles
						uncovered_perm = permutations(uncovered)
						for perm in uncovered_perm:
							# To keep track of which role needs to be marked as
							# 'with malus'
							indices = []

							# To keep track of the roles already checked
							already_malus = []

							# To check if a malus has been assigned to all
							# uncovered roles. If not, permutation is not valid
							count = 0

							# Check, position-wise, if uncovered roles can be
							# covered by the roles still available (with malus)
							for i in range(len(perm)):
								unc = perm[i]
								ava = available[i]

								# Select roles which are allowed to cover the
								# uncovered role
								unc_comp = dbf.db_select(
										table='malus',
										columns=['malus'],
										where=f'role = "{unc}"')[0]
								unc_comp = unc_comp.split(';')

								# If role avalable is not between them, skip to
								# next permutation
								if ava not in unc_comp:
									break

								# else, update count and mark the role with the
								# symbol '*' indicating the malus
								else:
									count += 1
									for k, rl in enumerate(lineup_roles):
										if (k not in already_malus and
										   rl == ava):

											indices.append((k, unc + '*'))
											already_malus.append(k)
											break

							# All the uncovered roles need to be covered by the
							# permutation. If not, continue with the next one
							if count != len(perm):
								continue

							# If permutation is able to cover all the uncovered
							# roles, update the parameters
							n_malus = len(perm)
							best_scheme = scheme

							# Replace the original roles with the ones marked
							# with '*'
							best_roles = lineup_roles.copy()
							for j, role in indices:
								best_roles[j] = role

							# Update best_lineup
							best_lineup = list(zip(lineup_names, best_roles))

	return best_lineup, best_scheme


def too_many_pc(players_roles):

	"""
	Once substitutes are added to players in field, filter if too many Pc.
	Different from filter_for_pc().

	:param players_roles: list

	:return: bool

	"""

	pc = sum([1 for pl, rl in players_roles if rl == 'Pc'])
	return True if pc > 2 else False


def save_mantra_lineup(day, fantateam, result):

	"""
	Save final lineup after mantra simulation.

	:param day: int
	:param fantateam: str
	:param result: list

	:return: nothing

	"""

	result = [f"{nm}:{rl}" for nm, rl in result]
	dbf.db_update(
			table='mantra_lineups',
			columns=[f'day_{day}'],
			values=[', '.join(result)],
			where=f'team_name="{fantateam}"')


def add_temporary_lineup_and_scheme_in_db(fantateam, day, lineup, scheme):

	"""
	Create a valid lineup in the db in order to allow mantra prediction.

	:param fantateam: str
	:param day: int
	:param lineup: list
	:param scheme: str

	"""

	# Fix names in lineup
	shortlist = dbf.db_select(table='all_players',
	                          columns=[f'day_{day-1}'],
	                          where=f'team_name="{fantateam}"')[0]
	shortlist = shortlist.split(', ')
	for i, pl in enumerate(lineup):
		new_pl = dbf.jaccard_result(in_opt=pl,
		                            all_opt=shortlist,
		                            ngrm=3)
		lineup[i] = new_pl

	# Update db
	dbf.db_update(table='lineups',
	              columns=[f'day_{day}'],
	              values=[', '.join(lineup)],
	              where=f'team_name = "{fantateam}"')
	dbf.db_update(table='schemes',
	              columns=[f'day_{day}'],
	              values=[scheme],
	              where=f'team_name = "{fantateam}"')


def clean_db_from_temporary_data(fantateam, day):

	"""
	Remove from db the temporary data used for mantra prediction.

	:param fantateam: str
	:param day: int

	"""

	dbf.db_update(table='lineups',
	              columns=[f'day_{day}'],
	              values=[''],
	              where=f'team_name = "{fantateam}"')

	dbf.db_update(table='schemes',
	              columns=[f'day_{day}'],
	              values=[''],
	              where=f'team_name = "{fantateam}"')


def predict_lineup(fantateam, players_out, day, lineup=None, scheme=None):

	"""
	Calculate the final lineup before all Serie A matches are completed.

	:param fantateam: str
	:param players_out: list
	:param day: int
	:param lineup: list or None
	:param scheme: str

	"""

	clean_db = True if lineup else False

	# Fix fantateam name
	all_fantateams = dbf.db_select(table='teams', columns=['team_name'])
	fantateam = dbf.jaccard_result(in_opt=fantateam,
	                               all_opt=all_fantateams,
	                               ngrm=3)

	# Check if day is already calculated
	mantra_lineup = dbf.db_select(table='mantra_lineups',
	                              columns=[f'day_{day}'],
	                              where=f'team_name="{fantateam}"')
	if mantra_lineup:
		print('Day already calculated')
		return

	# Insert lineup and scheme in the db if missing
	if lineup:
		add_temporary_lineup_and_scheme_in_db(fantateam=fantateam,
		                                      day=day,
		                                      lineup=lineup,
		                                      scheme=scheme)

	# Fix the names of the players which are not playing
	lineup = dbf.db_select(table='lineups',
	                       columns=[f'day_{day}'],
	                       where=f'team_name="{fantateam}"')[0]
	lineup = lineup.split(', ')

	for i, pl in enumerate(players_out):
		new_pl = dbf.jaccard_result(in_opt=pl,
		                            all_opt=lineup,
		                            ngrm=3)
		players_out[i] = new_pl

	# Add in the database a new entry for the players who will be included in
	# the lineup
	for player in lineup:
		if player not in players_out:
			dbf.db_insert(table='votes',
			              columns=['day', 'name', 'alvin'],
			              values=[day, player, 6])

	# Predict lineup
	predicted = mantra(day=day,
	                   fantateam=fantateam,
	                   starting_players=10,
	                   roles=True,
	                   save_lineup=False)

	dbf.db_delete(table='votes', where=f'day={day}')
	if clean_db:
		clean_db_from_temporary_data(fantateam=fantateam, day=day)

	# Print results
	field = lineup[:11]
	bench = lineup[11:]
	for (lineup, scheme, malus) in (predicted,):
		print('Malus: ', malus)
		print('Scheme: ', scheme)
		print(f'Players: {len(lineup)}')

		print('\nRegular:')
		for player in lineup:
			if player[0] in field:
				print(f'\t{player}')

		print(f'\nFrom bench:')
		for player in lineup:
			if player[0] in bench:
				print(f'\t{player}')


if __name__ == '__main__':

	predict_lineup(fantateam='bombagallo',
	               players_out=['farago', 'naingolan', 'sensi'],
	               day=5,
	               # lineup=['ospina',
	               #         'koulou', 'bonucci', 'toloi',
	               #         'biraghi', 'brozo', 'bonaventura', 'lazzari',
	               #         'de paul', 'cornelius', 'dzeko',
	               #         'mertens', 'inglese', 'missiroli', 'castro',
	               #         'asamoah', 'palomino', 'gunter', 'romero',
	               #         'klavan', 'tomovic', 'meret', 'karnezis'],
	               # scheme='3-4-1-2'
	               )
