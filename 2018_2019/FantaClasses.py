import db_functions as dbf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import mantra_functions as mf
import extra_functions as ef


class Player(object):

	def __init__(self, name):
		self.name = name

	def vote(self, day, source):

		"""
		Return player vote if any, else 'sv'.

		:param day: int
		:param source: str

		:return: int or str

		"""

		vote = dbf.db_select(
				table='votes',
				columns=[source],
				where='day={} AND name="{}"'.format(day, self.name))

		if vote:
			return vote[0]
		else:
			return 'sv'

	def bonus(self, day):

		"""
		Return the total amount of bonus relative to the player in a specific
		day.

		:param day: int
		:return: float

		"""

		features = ['gf', 'rp', 'rf', 'ass']
		values = [3, 3, 3, 1]

		points = dbf.db_select(
				table='votes',
				columns=features,
				where='day={} AND name="{}"'.format(day, self.name))[0]

		return sum(np.multiply(points, values))

	def malus(self, day):

		"""
		Return the total amount of malus relative to the player in a specific
		day.

		:param day: int
		:return: float

		"""

		features = ['gs', 'rs', 'au', 'amm', 'esp']
		values = [1, 3, 2, .5, 1]

		points = dbf.db_select(
				table='votes',
				columns=features,
				where='day={} AND name="{}"'.format(day, self.name))[0]

		return sum(np.multiply(points, values))

	def fantavote(self, day, source):

		"""
		Return the fantavote of the player.

		:param day: int
		:param source: str

		:return: float

		"""

		return self.vote(day, source) + self.bonus(day) - self.malus(day)


class Fantateam(object):

	def __init__(self, name):
		self.name = name
		self.points = []
		self.victories = 0
		self.draws = 0
		self.defeats = 0
		self.goals_scored = []
		self.goals_taken = []
		self.goals_diff = 0
		self.abs_points = []
		self.malus = 0
		self.half_point = 0
		self.matches_in_ten = 0
		self.matches_in_nine = 0
		self.onezero = 0
		self.one_goal_win = 0
		self.one_goal_lose = 0
		self.zerogoals = 0


class FastFantateam(object):

	def __init__(self, name):
		self.name = name
		self.points = 0
		self.abs_points = 0


class Match(object):

	def __init__(self, team1, team2, day, all_players, source):

		"""
		:param team1: Fantateam() instance
		:param team2: Fantateam() instance
		:param day: int
		:param all_players: dict, Ex: player_name: Player() instance
		:param source: str, Options: alvin, italia, fg

		"""
		self.team1 = team1
		self.team2 = team2
		self.day = day
		self.all_players = all_players
		self.source = source
		self.result = None

		self.play_match()

	def play_match(self):

		"""
		Define lineups and update all the attributes of each fantateam.
		To make it faster, lineups are defined in two ways depending on the
		case:

			1. First we look in the database in the 'mantra_lineups' table to
			   check if they  ahve been already calculated.

			2. If not found we run the mantra algorithm to calculate them

		:return: nothing

		"""

		# To save time, try to find mantra lineups already calculated
		try:
			lineup1 = dbf.db_select(
					table='mantra_lineups',
					columns=['day_{}'.format(self.day)],
					where='team_name="{}"'.format(self.team1.name))[0].\
				split(', ')
			lineup1 = [tuple(el.split(':')) for el in lineup1]

			lineup2 = dbf.db_select(
					table='mantra_lineups',
					columns=['day_{}'.format(self.day)],
					where='team_name="{}"'.format(self.team2.name))[0].\
				split(', ')
			lineup2 = [tuple(el.split(':')) for el in lineup2]

			malus1 = sum([1 for nm, rl in lineup1 if '*' in rl])
			malus2 = sum([1 for nm, rl in lineup2 if '*' in rl])

			lineup1 = [nm for nm, rl in lineup1]
			lineup2 = [nm for nm, rl in lineup2]

		# if not found, calculate them with mantra algorithm
		except IndexError:
			lineup1, _, malus1 = mf.mantra(day=self.day,
			                               fantateam=self.team1.name,
			                               starting_players=mf.START_PLAYERS,
			                               source=self.source,
			                               roles=False)
			lineup2, _, malus2 = mf.mantra(day=self.day,
			                               fantateam=self.team2.name,
			                               starting_players=mf.START_PLAYERS,
			                               source=self.source,
			                               roles=False)

		self.update_fantateams_data(lineup1, lineup2, malus1, malus2)

	def update_fantateams_data(self, lineup1, lineup2, malus1, malus2):

		abs_points1 = sum(
				[self.all_players[pl].fantavote(self.day, self.source)
				 for pl in lineup1]) - malus1
		abs_points2 = sum(
				[self.all_players[pl].fantavote(self.day, self.source)
				 for pl in lineup2]) - malus2

		goals1 = int(max(abs_points1 - 60, 0) // 6)
		goals2 = int(max(abs_points2 - 60, 0) // 6)

		self.result = '{}   ({}){} - {}({})   {}'.format(
				self.team1.name, abs_points1, goals1,
				goals2, abs_points2, self.team2.name)

		self.team1.abs_points.append(abs_points1)
		self.team1.goals_scored.append(goals1)
		self.team1.goals_taken.append(goals2)
		self.team1.goals_diff += goals1 - goals2
		self.team1.malus += malus1

		self.team2.abs_points.append(abs_points2)
		self.team2.goals_scored.append(goals2)
		self.team2.goals_taken.append(goals1)
		self.team2.goals_diff += goals2 - goals1
		self.team2.malus += malus2

		if goals1 == goals2:
			self.team1.points.append(1)
			self.team1.draws += 1
			self.team2.points.append(1)
			self.team2.draws += 1

		elif goals1 > goals2:
			self.team1.points.append(3)
			self.team1.victories += 1
			self.team2.points.append(0)
			self.team2.defeats += 1

		else:
			self.team2.points.append(3)
			self.team2.victories += 1
			self.team1.points.append(0)
			self.team1.defeats += 1

		if len(lineup1) == 10:
			self.team1.matches_in_ten += 1
		elif len(lineup1) == 9:
			self.team1.matches_in_nine += 1

		if len(lineup2) == 10:
			self.team2.matches_in_ten += 1
		elif len(lineup2) == 9:
			self.team2.matches_in_nine += 1

		if goals1 + goals2 == 1 and goals1:
			self.team1.onezero += 1
		elif goals1 + goals2 == 1 and goals2:
			self.team2.onezero += 1
		elif goals1 - goals2 == 1:
			self.team1.one_goal_win += 1
			self.team2.one_goal_lose += 1
		elif goals2 - goals1 == 1:
			self.team2.one_goal_win += 1
			self.team1.one_goal_lose += 1

		if not goals1:
			self.team1.zerogoals += 1
		if not goals2:
			self.team2.zerogoals += 1

		self.update_half_point(abs_points1, abs_points2)

	def update_half_point(self, abs_points1, abs_points2):

		# Scores have to be different from each other
		cond1 = abs_points1 != abs_points2

		# Their difference has to be small, maximum 5.5
		cond2 = abs(abs_points1 - abs_points2) < 6

		# At least 1 of them needs to be minimum 65.5
		cond3 = max([abs_points1, abs_points2]) >= 65.5

		if cond1 and cond2 and cond3:

			rest1 = abs_points1 % 6
			rest2 = abs_points2 % 6

			data = [(self.team1, abs_points1, rest1),
			        (self.team2, abs_points2, rest2)]
			data.sort(key=lambda x: x[1])

			lower, higher = data

			if higher[2] == 5.5 or lower[2] == 0:
				higher[0].half_point -= 2
				lower[0].half_point += 1

			if lower[2] == 5.5 or higher[2] == 0:
				higher[0].half_point += 2
				lower[0].half_point -= 1


class FastMatch(object):

	def __init__(self, team1, team2, day, abs_points, source):

		self.team1 = team1
		self.team2 = team2
		self.day = day
		self.abs_points1 = abs_points[self.team1.name][self.day - 1]
		self.abs_points2 = abs_points[self.team2.name][self.day - 1]
		self.source = source

		self.update_fantateams_data(self.abs_points1, self.abs_points2)

	def update_fantateams_data(self, abs_points1, abs_points2):

		goals1 = int(max(abs_points1 - 60, 0) // 6)
		goals2 = int(max(abs_points2 - 60, 0) // 6)

		self.team1.abs_points += abs_points1
		self.team2.abs_points += abs_points2

		if goals1 == goals2:
			self.team1.points += 1
			self.team2.points += 1

		elif goals1 > goals2:
			self.team1.points += 3

		else:
			self.team2.points += 3


class League(object):

	def __init__(self, fteams, a_round, n_days, all_players, source):
		self.fteams = {ft: Fantateam(ft) for ft in fteams}
		self.a_round = a_round
		self.n_days = n_days
		self.all_players = all_players
		self.source = source
		self.schedule = ef.generate_schedule(a_round, self.n_days)
		self.matches = []

		self.play_league()
		self.ranking = None
		self.main_info = self.create_ranking(n_days)
		self.info = self.info(n_days)

	def play_league(self):

		for day, matches in enumerate(self.schedule, 1):
			for match in matches:
				team1, team2 = match.split(' - ')
				m = Match(self.fteams[team1], self.fteams[team2], day,
				          self.all_players, self.source)

				self.matches.append(m)

	def sort_by_classifica_avulsa(self, dataframe):

		df = dataframe.copy()
		mutable_index = df.index

		values = df['Pt'].value_counts()
		values = values[values > 1].index

		for value in values:
			sub_df = df[df['Pt'] == value]
			mutable_index = np.array([x if x not in sub_df.index else 'Unknown'
			                          for x in mutable_index], dtype='object')
			sub_df = self.mini_ranking(sub_df)
			mutable_index[mutable_index == 'Unknown'] = sub_df.index
			df = df.reindex(mutable_index)

		return df

	def mini_ranking(self, dataframe):

		df = dataframe.copy()
		df['CA'] = 0

		teams = list(df.index)
		teams_dict = {team: 0 for team in teams}
		sub_matches = list(mf.combinations(teams, 2))
		sub_matches = [set(match) for match in sub_matches]

		for i, day in enumerate(self.schedule):
			for match in day:
				match = set(match.split(' - '))

				for sub_match in sub_matches:
					if not sub_match - match:
						tm1, tm2 = match

						teams_dict[tm1] += self.fteams[tm1].points[i]
						teams_dict[tm2] += self.fteams[tm2].points[i]

		df['CA'] = df.index.map(teams_dict)
		df.sort_values(by='CA', ascending=False, inplace=True)
		df.drop('CA', axis=1, inplace=True)

		return df

	def create_ranking(self, days):

		data = {}

		for ft in self.fteams:
			data[ft] = (days, self.fteams[ft].victories,
			            self.fteams[ft].draws,
			            self.fteams[ft].defeats,
			            sum(self.fteams[ft].goals_scored),
			            sum(self.fteams[ft].goals_taken),
			            self.fteams[ft].goals_diff,
			            sum(self.fteams[ft].points),
			            sum(self.fteams[ft].abs_points))

		cols = ['G', 'V', 'N', 'P', 'G+', 'G-', 'Dr', 'Pt', 'Tot Pt']
		df = pd.DataFrame.from_dict(data, orient='index', columns=cols)

		df.sort_values(by='N', ascending=False, inplace=True)
		df.sort_values(by='V', ascending=False, inplace=True)
		df.sort_values(by='G+', ascending=False, inplace=True)
		df.sort_values(by='Dr', ascending=False, inplace=True)
		df = self.sort_by_classifica_avulsa(df)
		df.sort_values(by='Tot Pt', ascending=False, inplace=True)
		df.sort_values(by='Pt', ascending=False, inplace=True)

		self.ranking = df.index

		return df.style.set_properties(**{'width': '50px'}). \
			set_properties(subset=['Pt'], **{'font-weight': 'bold'})

	# noinspection PyTypeChecker
	def info(self, days):

		data = []
		index = self.main_info.index

		for ft in index:
			info = (round(sum(self.fteams[ft].points) / days, 2),
			        round(sum(self.fteams[ft].abs_points) / days, 2),
			        round(np.std(self.fteams[ft].goals_scored), 2),
			        round(np.std(self.fteams[ft].goals_taken), 2),
			        self.fteams[ft].malus,
			        self.fteams[ft].half_point,
			        self.fteams[ft].matches_in_ten,
			        self.fteams[ft].matches_in_nine,
			        self.fteams[ft].onezero,
			        self.fteams[ft].one_goal_win,
			        self.fteams[ft].one_goal_lose,
			        self.fteams[ft].zerogoals)

			data.append(info)

		cols = ['M Pt', 'M Tot Pt', 's+', 's-', 'Malus', '1/2',
		        'In 10', 'In 9', '1-0', '+1 Gol', '-1 Gol', '< 66']
		df = pd.DataFrame(data, index=index, columns=cols)

		return df.style.set_properties(**{'width': '60px'})

	def switch_teams_in_round(self, team1, team2):

		new_round = [[match.replace(team1, 'XXX') for match in day]
		             for day in self.a_round]
		new_round = [[match.replace(team2, team1) for match in day]
		             for day in new_round]
		new_round = [[match.replace('XXX', team2) for match in day]
		             for day in new_round]
		new_round = [[(tm1, tm2) for x in i for tm1, tm2 in
		              (x.split(' - '),)] for i in new_round]

		return new_round

	def create_heatmap(self):

		teams = self.ranking
		points = {tm: sum(self.fteams[tm].points) for tm in teams}

		df = pd.DataFrame(0, index=teams, columns=teams)

		for tm1 in teams:
			for tm2 in teams:

				if tm1 == tm2 or df.loc[tm1, tm2]:
					continue

				new_round = self.switch_teams_in_round(tm1, tm2)

				new_teams = {ft: Fantateam(ft) for ft in self.fteams}

				abs_points = create_abs_points_dict(new_teams, self.n_days)

				new_lg = FastLeague(new_teams, abs_points, new_round,
				                    self.n_days, self.source)

				idx1 = np.argwhere(new_lg.ranking[0] == tm1).flatten()
				idx2 = np.argwhere(new_lg.ranking[0] == tm2).flatten()

				pt1 = new_lg.ranking[1][idx1][0]
				pt2 = new_lg.ranking[1][idx2][0]

				df.loc[tm1, tm2] = pt1 - points[tm1]
				df.loc[tm2, tm1] = pt2 - points[tm2]

		fig, ax = plt.subplots(figsize=(6, 6))
		fig.subplots_adjust(left=.3, bottom=.3)
		ax.tick_params(axis='both', labelsize=10)

		return sns.heatmap(df, annot=True, annot_kws={"size": 12},
		                   cmap='YlGn_r', square=True, cbar=False)


class FastLeague(object):

	def __init__(self, fteams, abs_points, a_round, n_days, source):

		self.fteams = {ft: FastFantateam(ft) for ft in fteams}
		self.abs_points = abs_points
		self.a_round = a_round
		self.source = source
		self.schedule = ef.generate_schedule(a_round, n_days)

		self.play_league()
		self.ranking = self.create_ranking(n_days)

	def play_league(self):

		for day, matches in enumerate(self.schedule, 1):
			for team1, team2 in matches:
				FastMatch(self.fteams[team1], self.fteams[team2], day,
				          self.abs_points, self.source)

	def create_ranking(self, days):

		data = {}

		for ft in self.fteams:
			data[ft] = (days, self.fteams[ft].points,
			            self.fteams[ft].abs_points)

		cols = ['G', 'Pt', 'Tot Pt']
		df = pd.DataFrame.from_dict(data, orient='index', columns=cols)

		df.sort_values(by='Tot Pt', ascending=False, inplace=True)
		df.sort_values(by='Pt', ascending=False, inplace=True)

		return df.index, df['Pt'].values


class Calendar(object):

	def __init__(self, fteams, n_leagues, n_days, source):

		self.teams = {team: Fantateam(team) for team in fteams}
		self.abs_points = create_abs_points_dict(self.teams, n_days)
		self.positions = {i: {team: 0 for team in fteams} for i in range(1, 9)}
		self.archive = {i: {team: [] for team in fteams} for i in range(1, 9)}
		self.rounds = ef.random_rounds(n_leagues)
		self.max_pt = {team: 0 for team in fteams}
		self.min_pt = {team: 1e6 for team in fteams}
		self.avg = {team: 0 for team in fteams}

		self.simulation(fteams, n_days, source)

		self.stats = self.stats(fteams)

	def simulation(self, teams, n_days, source):

		for a_round in self.rounds:

			lg = FastLeague(teams, self.abs_points, a_round, n_days, source)

			names, points = lg.ranking
			for pos, tm in enumerate(names, 1):
				self.positions[pos][tm] += (1 / len(self.rounds))*100

				if points[pos - 1] > self.max_pt[tm]:
					self.max_pt[tm] = points[pos - 1]

				if points[pos - 1] < self.min_pt[tm]:
					self.min_pt[tm] = points[pos - 1]

				self.archive[pos][tm].append(a_round)

				self.avg[tm] += points[pos - 1] / len(self.rounds)

	def stats(self, teams):

		pos = []
		for team in teams:
			pos.append((team, [round(self.positions[i][team], 1)
			                   for i in range(1, 9)]))

		sorted_data = []
		for i in range(len(teams)):
			pos.sort(key=lambda x: sum(x[1][0:i + 1]), reverse=True)
			sorted_data.append(pos[0])
			pos = pos[1:]

		teams = [nm for nm, _ in sorted_data]
		pos = [dt for _, dt in sorted_data]
		points = [[round(self.avg[nm], 1), self.max_pt[nm], self.min_pt[nm]]
		          for nm, _ in sorted_data]

		data = [pos[i] + points[i] for i in range(len(teams))]

		cols = ['1°(%)', '2°(%)', '3°(%)', '4°(%)',
		        '5°(%)', '6°(%)', '7°(%)', '8°(%)', 'Media', 'Max', 'Min']
		df = pd.DataFrame(data, index=teams, columns=cols)

		return df.style.set_properties(**{'width': '50px'})

	def specific_round(self, team, position, n_days):

		res = self.archive[position][team]
		n_leagues = sum([len(self.archive[i][team]) for i in range(1, 9)])
		if not res:
			print('{} mai in {}° posizione.'.format(team, position))
			return None, None
		else:
			if len(res) == 1:
				name = 'campionato'
			else:
				name = 'campionati'

			print('{} in {}° posizione: {} {} su {}.'.format(
					team, position, len(res), name, n_leagues))

			rn = [['{} - {}'.format(tm1, tm2) for tm1, tm2 in el]
			      for el in res[0]]

			rn_complete = ef.generate_schedule(rn, n_days)

			data = []
			for day, matches in enumerate(rn_complete, 1):
				for match in matches:
					tm1, tm2 = match.split(' - ')
					data.append((match, get_result(tm1, tm2, day)))

			new_data = []
			added = []
			for match, _ in data:
				if match not in added:
					results = [r for m, r in data if m == match]
					while len(results) < 5:
						results.append(' ')
					results.insert(0, match)
					new_data.append(results)
					added.append(match)

			data = []
			for i in range(0, 25, 4):
				for j in range(i, i+4):
					data.append(new_data[j])
				data.append([' '*(i//4), ' ', ' ', ' ', ' ', ' '])

			df = pd.DataFrame(data, columns=['N', '1°', '2°', '3°', '4°', '5°'])
			df.set_index('N', drop=True, inplace=True)
			df.index.name = None

			return df.style.set_properties(**{'width': '50px'}), rn


def create_abs_points_dict(fteams, n_days):

	abs_points = {tm: None for tm in fteams}

	for tm in abs_points:
		abs_points[tm] = dbf.db_select(
				table='absolute_points',
				columns=['day_{}'.format(day) for day in range(1, n_days + 1)],
				where='team_name="{}"'.format(tm))[0]

	return abs_points


def get_result(team1, team2, day):

	abs_points1 = dbf.db_select(
			table='absolute_points',
			columns=['day_{}'.format(day)],
			where='team_name="{}"'.format(team1))[0]
	abs_points2 = dbf.db_select(
			table='absolute_points',
			columns=['day_{}'.format(day)],
			where='team_name="{}"'.format(team2))[0]

	goals1 = int(max(abs_points1 - 60, 0) // 6)
	goals2 = int(max(abs_points2 - 60, 0) // 6)

	return '{} - {}'.format(goals1, goals2)


def average_global_std(fteams, days, n_leagues, iterations):

	avg_std = {team: [] for team in fteams}

	for i in range(iterations):
		cl = Calendar(fteams, n_leagues, days, 'alvin')
		positions = cl.positions

		for team in fteams:
			res = []
			for pos in positions:
				res.append(positions[pos][team])
			avg_std[team].append(res)

	avg_std = [np.mean(np.array(avg_std[tm]).std(axis=0)) for tm in avg_std]
	avg_std = np.mean(avg_std)

	return avg_std


def optimal_number_iterations(fteams, days, leagues_options,
                              iter_each_option, verbose):

	results = []
	for iters in leagues_options:
		results.append(average_global_std(fteams, days, iters,
		                                  iter_each_option))
		if verbose:
			print(iters)

	return results


players = set(dbf.db_select(table='votes', columns=['name']))
fantateams = dbf.db_select(table='teams', columns=['team_name'])
players = {pl: Player(pl) for pl in players}
our_round = [dbf.db_select(table='round',
                           columns=['day_{}'.format(i)])
             for i in range(1, len(fantateams))]
DAYS = 5

lg = League(fantateams, our_round, DAYS, players, 'alvin')
# a = lg.create_heatmap()
# print()
# print(lg.ranking)
# a = Calendar(fantateams, 20, DAYS, 'alvin')
# a.specific_round('Ciolle United', 1, DAYS)
# optimal_number_iterations(fantateams, DAYS, [10, 40], 3, False)
