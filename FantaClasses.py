import db_functions as dbf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import mantra_functions as mf
import extra_functions as ef
from update_database import last_day_played
from IPython.display import display


class Fantateam(object):

	def __init__(self, name: str):
		self.name = name
		self.points = []
		self.victories = 0
		self.draws = 0
		self.defeats = 0
		self.goals_scored = []
		self.goals_taken = []
		self.goals_diff = 0
		self.abs_points = []
		self.half_point = 0
		self.onezero = 0
		self.one_goal_win = 0
		self.one_goal_lose = 0
		self.zerogoals = 0
		self.captain_bonus_malus_balance = 0
		self.rfactor_bonus_malus_balance = 0


class Match(object):

	def __init__(
			self,
			team1: Fantateam,
			team2: Fantateam,
			day: int,
			use_rfactor: bool,
			use_captain: bool
	):

		self.team1 = team1
		self.team2 = team2
		self.day = day
		self.use_rfactor = use_rfactor
		self.use_captain = use_captain

		self.play_match()

	def play_match(self):

		# Get raw data team1
		abs_points1, rfactor1, captain1 = get_points(
				team_name=self.team1.name,
				day=self.day,
				use_rfactor=self.use_rfactor,
				use_captain=self.use_captain
		)

		# Get raw data team2
		abs_points2, rfactor2, captain2 = get_points(
				team_name=self.team2.name,
				day=self.day,
				use_rfactor=self.use_rfactor,
				use_captain=self.use_captain
		)

		# Compute total points
		abs_points1 += rfactor1 + captain1
		abs_points2 += rfactor2 + captain2

		# From abs_points calculate corresponding goals
		goals1 = int(max(abs_points1 - 60, 0) // 6)
		goals2 = int(max(abs_points2 - 60, 0) // 6)

		# Update abs_points, rfactor and captain
		self.team1.abs_points.append(abs_points1)
		self.team1.rfactor_bonus_malus_balance += rfactor1
		self.team1.captain_bonus_malus_balance += captain1
		self.team2.abs_points.append(abs_points2)
		self.team2.rfactor_bonus_malus_balance += rfactor2
		self.team2.captain_bonus_malus_balance += captain2

		# Update goals
		self.team1.goals_scored.append(goals1)
		self.team1.goals_taken.append(goals2)
		self.team1.goals_diff += goals1 - goals2
		self.team2.goals_scored.append(goals2)
		self.team2.goals_taken.append(goals1)
		self.team2.goals_diff += goals2 - goals1

		# Update victories, draws and defeats
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

		# Update 1-0 victories
		if goals1 + goals2 == 1 and goals1:
			self.team1.onezero += 1
		elif goals1 + goals2 == 1 and goals2:
			self.team2.onezero += 1

		# Update 1-goal victories and defeats
		elif goals1 - goals2 == 1:
			self.team1.one_goal_win += 1
			self.team2.one_goal_lose += 1
		elif goals2 - goals1 == 1:
			self.team2.one_goal_win += 1
			self.team1.one_goal_lose += 1

		# Update 0 goals matches
		if not goals1:
			self.team1.zerogoals += 1
		if not goals2:
			self.team2.zerogoals += 1

		self.update_half_point(abs_points1, abs_points2)

	def update_half_point(self, abs_points1: float, abs_points2: float) -> None:

		"""
		Update the attribute 'half_points' for each fantateam. It describes
		the number of points the fantateam has gained (if positive) or lost
		(if negative) thanks to 0.5.
		"""

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


class League(object):

	def __init__(
			self,
			fantateams: [str],
			schedule: [[str]],
			n_days: int,
			use_rfactor: bool,
			use_captain: bool
	):

		self.fantateams = {ft: Fantateam(ft) for ft in fantateams}
		self.schedule = schedule
		self.n_days = n_days
		self.use_rfactor = use_rfactor
		self.use_captain = use_captain
		self.matches = []

		self.play_league()
		self.ranking = None

	def play_league(self):

		for day, matches in enumerate(self.schedule, 1):
			for match in matches:
				team1, team2 = match.split(' - ')
				m = Match(
						team1=self.fantateams[team1],
						team2=self.fantateams[team2],
						day=day,
						use_rfactor=self.use_rfactor,
						use_captain=self.use_captain)
				self.matches.append(m)

	def sort_by_classifica_avulsa(self, ranking: pd.DataFrame) -> pd.DataFrame:

		rank = ranking.copy()
		mutable_index = rank.index

		values = rank['Pt'].value_counts()
		values = values[values > 1].index

		for value in values:
			sub_df = rank[rank['Pt'] == value]
			mutable_index = np.array([x if x not in sub_df.index else 'Unknown'
			                          for x in mutable_index], dtype='object')
			sub_df = self.mini_ranking(sub_df)
			mutable_index[mutable_index == 'Unknown'] = sub_df.index
			rank = rank.reindex(mutable_index)

		return rank

	def mini_ranking(self, ranking: pd.DataFrame) -> pd.DataFrame:

		"""
		Order each subgroup of teams with the same points according to the
		matches they played between themselves.
		"""

		rank = ranking.copy()
		rank['CA'] = 0

		fteams = rank.index
		fteams_dict = {team: 0 for team in fteams}
		sub_matches = mf.itertools.combinations(fteams, 2)
		sub_matches = [set(match) for match in sub_matches]

		for i, day in enumerate(self.schedule):
			for match in day:
				match = set(match.split(' - '))

				for sub_match in sub_matches:
					if not sub_match - match:
						tm1, tm2 = match

						fteams_dict[tm1] += self.fantateams[tm1].points[i]
						fteams_dict[tm2] += self.fantateams[tm2].points[i]

		rank['CA'] = rank.index.map(fteams_dict)
		rank.sort_values(by='CA', ascending=False, inplace=True)
		rank.drop('CA', axis=1, inplace=True)

		return rank

	def create_ranking(self, double_check=True):
		
		data = {ft: (
			self.n_days,
			self.fantateams[ft].victories,
			self.fantateams[ft].draws,
			self.fantateams[ft].defeats,
			sum(self.fantateams[ft].goals_scored),
			sum(self.fantateams[ft].goals_taken),
			self.fantateams[ft].goals_diff,
			sum(self.fantateams[ft].points),
			sum(self.fantateams[ft].abs_points)) for ft in self.fantateams
		}

		cols = ['G', 'V', 'N', 'P', 'G+', 'G-', 'Dr', 'Pt', 'Tot Pt']
		ranking = pd.DataFrame.from_dict(data, orient='index', columns=cols)
		if double_check:
			assert_df_is_correct(ranking)

		ranking.sort_values(by='N', ascending=False, inplace=True)
		ranking.sort_values(by='V', ascending=False, inplace=True)
		ranking.sort_values(by='Dr', ascending=False, inplace=True)
		ranking.sort_values(by='G+', ascending=False, inplace=True)
		ranking = self.sort_by_classifica_avulsa(ranking)
		ranking.sort_values(by='Tot Pt', ascending=False, inplace=True)
		ranking.sort_values(by='Pt', ascending=False, inplace=True)
		self.ranking = ranking.index

		return ranking.style.set_properties(
				**{'width': '50px'}).set_properties(
				subset=['Pt'], **{'font-weight': 'bold'}).format(
				'{:.1f}', subset=['Tot Pt'])

	# noinspection PyTypeChecker
	def extra_info(self) -> pd.DataFrame:

		data = {
			ft: (
				round(sum(self.fantateams[ft].points) / self.n_days, 2),
				round(sum(self.fantateams[ft].abs_points) / self.n_days, 2),
				round(np.std(self.fantateams[ft].goals_scored), 2),
				round(np.std(self.fantateams[ft].goals_taken), 2),
				self.fantateams[ft].half_point,
				self.fantateams[ft].onezero,
				self.fantateams[ft].one_goal_win,
				self.fantateams[ft].one_goal_lose,
				self.fantateams[ft].zerogoals,
				self.fantateams[ft].rfactor_bonus_malus_balance,
				self.fantateams[ft].captain_bonus_malus_balance
			) for ft in self.ranking
		}

		cols = ['M Pt', 'M Tot Pt', 's+', 's-', '1/2',
		        '1-0', '+1 Gol', '-1 Gol', '< 66', 'RF', 'C']
		df = pd.DataFrame.from_dict(data, orient='index', columns=cols)

		df = df.style.set_properties(**{'width': '60px'}).format(
				'{:.2f}', subset=['M Pt', 'M Tot Pt', 's+', 's-'])
		return df.format('{:.1f}', subset=['RF', 'C'])

	def switch_teams_in_round(self, team1: str, team2: str) -> list:

		"""
		Create a new round where team1 and team2 are switched.
		Used inside create_heatmap().
		"""

		new_schedule = [[match.replace(team1, 'XXX') for match in day]
		                for day in self.schedule]
		new_schedule = [[match.replace(team2, team1) for match in day]
		                for day in new_schedule]
		new_schedule = [[match.replace('XXX', team2) for match in day]
		                for day in new_schedule]
		new_schedule = [[f'{tm1} - {tm2}' for x in i for tm1, tm2 in
		                 (x.split(' - '),)] for i in new_schedule]

		return new_schedule

	def create_heatmap(self):

		points = {tm: sum(self.fantateams[tm].points) for tm in self.ranking}

		df = pd.DataFrame(0, index=self.ranking, columns=self.ranking)

		dict_abs_points = generate_points_dict(
				fantateams=self.fantateams.keys(),
				n_days=self.n_days
		)
		for tm1 in self.ranking:
			for tm2 in self.ranking:

				if tm1 == tm2 or df.loc[tm1, tm2]:
					continue

				new_schedule = self.switch_teams_in_round(tm1, tm2)

				new_teams = {ft: FastFantateam(ft) for ft in self.fantateams}

				new_lg = FastLeague(
						fantateams=new_teams,
						schedule=new_schedule,
						n_days=self.n_days,
						dict_abs_points=dict_abs_points
				)

				idx1 = np.argwhere(new_lg.ranking[0] == tm1).flatten()
				idx2 = np.argwhere(new_lg.ranking[0] == tm2).flatten()

				pt1 = new_lg.ranking[1][idx1][0]
				pt2 = new_lg.ranking[1][idx2][0]

				df.loc[tm1, tm2] = pt1 - points[tm1]
				df.loc[tm2, tm1] = pt2 - points[tm2]

		fig, ax = plt.subplots(figsize=(6, 6))
		fig.subplots_adjust(left=.3, bottom=.3)
		ax.tick_params(axis='both', labelsize=10)

		sns.heatmap(df, annot=True, annot_kws={"size": 12},
		            cmap='YlGn_r', square=True, cbar=False)
		plt.show()


class FastFantateam(object):

	def __init__(self, name: str):
		self.name = name
		self.points = 0
		self.abs_points = 0


class FastMatch(object):

	def __init__(
			self,
			team1: FastFantateam,
			team2: FastFantateam,
			day: int,
			abs_points: dict
	):

		self.team1 = team1
		self.team2 = team2
		self.day = day
		self.abs_points1 = abs_points[self.team1.name][self.day-1]
		self.abs_points2 = abs_points[self.team2.name][self.day-1]

		self.update_fantateams_data(self.abs_points1, self.abs_points2)

	def update_fantateams_data(self, abs_points1: float, abs_points2: float):

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


class FastLeague(object):

	def __init__(
			self,
			fantateams: [str],
			schedule: [[str]],
			n_days: int,
			dict_abs_points: dict
	):

		self.fantateams = {ft: FastFantateam(ft) for ft in fantateams}
		self.schedule = schedule
		self.n_days = n_days
		self.abs_points = dict_abs_points

		self.play_league()
		self.ranking = self.create_ranking(n_days)

	def play_league(self):

		for day, matches in enumerate(self.schedule, 1):
			for match in matches:
				team1, team2 = match.split(' - ')
				FastMatch(
						team1=self.fantateams[team1],
						team2=self.fantateams[team2],
						day=day,
						abs_points=self.abs_points
				)

	def create_ranking(self, days):

		data = {
			ft: (
				days,
				self.fantateams[ft].points,
				self.fantateams[ft].abs_points) for ft in self.fantateams
		}

		cols = ['G', 'Pt', 'Tot Pt']
		df = pd.DataFrame.from_dict(data, orient='index', columns=cols)

		df.sort_values(by='Tot Pt', ascending=False, inplace=True)
		df.sort_values(by='Pt', ascending=False, inplace=True)

		return df.index, df['Pt'].values


class Calendar(object):

	def __init__(
			self,
			fantateams: str,
			n_leagues: int,
			n_days: int
	):

		self.fantateams = {team: Fantateam(team) for team in fantateams}
		self.n_leagues = n_leagues
		self.n_days = n_days
		self.positions = {
			i: {team: 0 for team in self.fantateams} for i in range(1, 9)
		}
		self.archive = {
			i: {team: [] for team in self.fantateams} for i in range(1, 9)
		}
		self.schedules = ef.random_asymmetric_schedules(
				n_schedules=self.n_leagues,
				n_days=self.n_days
		)
		self.max_pt = {ft: 0 for ft in self.fantateams}
		self.min_pt = {ft: 100 for ft in self.fantateams}
		self.avg = {ft: 0 for ft in self.fantateams}
		self.dict_abs_points = generate_points_dict(
				fantateams=self.fantateams.keys(),
				n_days=self.n_days
		)

		self.simulation()

		for pos in self.archive:
			for ft in self.archive[pos]:
				self.archive[pos][ft].sort(key=lambda x: x[0], reverse=True)
				self.archive[pos][ft] = [rn for _, rn in self.archive[pos][ft]]

		self.stats = self.stats()

	def simulation(self):

		for i, sched in enumerate(self.schedules, 1):

			fl = FastLeague(
					fantateams=self.fantateams,
					schedule=sched,
					n_days=self.n_days,
					dict_abs_points=self.dict_abs_points
			)

			names, points = fl.ranking

			for pos, tm in enumerate(names, 1):
				self.positions[pos][tm] += (1 / len(self.schedules))*100

				if points[pos - 1] > self.max_pt[tm]:
					self.max_pt[tm] = points[pos - 1]

				if points[pos - 1] < self.min_pt[tm]:
					self.min_pt[tm] = points[pos - 1]

				self.archive[pos][tm].append((points[pos - 1], sched))

				self.avg[tm] += points[pos - 1] / len(self.schedules)

			print(f'\rCampionati giocati: {i}/{len(self.schedules)}', end='')

	def stats(self):

		pos = [
			(ft, [round(self.positions[i][ft], 1) for i in range(1, 9)])
			for ft in self.fantateams]

		sorted_data = []
		for i in range(len(self.fantateams)):
			pos.sort(key=lambda x: sum(x[1][0:i + 1]), reverse=True)
			sorted_data.append(pos[0])
			pos = pos[1:]

		fts = [nm for nm, _ in sorted_data]
		pos = [dt for _, dt in sorted_data]
		points = [[round(self.avg[nm], 1), self.max_pt[nm], self.min_pt[nm]]
		          for nm, _ in sorted_data]

		data = [pos[i] + points[i] for i in range(len(fts))]

		cols = ['1°(%)', '2°(%)', '3°(%)', '4°(%)',
		        '5°(%)', '6°(%)', '7°(%)', '8°(%)', 'Media', 'Max', 'Min']
		df = pd.DataFrame(data, index=fts, columns=cols)

		return df.style.set_properties(**{'width': '50px'}).format(
				'{:.1f}',
				subset=['1°(%)', '2°(%)', '3°(%)', '4°(%)',
				        '5°(%)', '6°(%)', '7°(%)', '8°(%)', 'Media'])

	def get_result(self, fantateam1: str, fantateam2: str, day: int) -> str:

		abs_points1 = self.dict_abs_points[fantateam1][day-1]
		abs_points2 = self.dict_abs_points[fantateam2][day-1]

		goals1 = int(max(abs_points1 - 60, 0) // 6)
		goals2 = int(max(abs_points2 - 60, 0) // 6)

		return f'{goals1} - {goals2}'

	def specific_round(self, fantateam: str, position: int) -> None:

		"""
		If any, print one of the rounds where team "team" ends in position
		"position".
		"""

		# Load corresponding calendars and print some info
		res = self.archive[position][fantateam]
		if not res:
			print(f'{fantateam} mai in {position}° posizione.')
		else:
			if len(res) == 1:
				name = 'campionato'
			else:
				name = 'campionati'

			print(f'{fantateam} in {position}° posizione: '
			      f'{len(res)} {name} su {self.n_leagues}.')

			# Create data: match and result
			a_schedule = res[0]
			data = []
			for day, matches in enumerate(res[0], 1):
				for match in matches:
					tm1, tm2 = match.split(' - ')
					data.append((match, self.get_result(tm1, tm2, day)))

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
					try:
						data.append(new_data[j])
					except IndexError:
						break
				data.append([' '*(i//4), ' ', ' ', ' ', ' ', ' '])

			df = pd.DataFrame(data, columns=['N', '1°', '2°', '3°', '4°', '5°'])
			df.set_index('N', drop=True, inplace=True)
			df.index.name = None

			# sp = League(fteams=fantateams,
		    #             a_round=rn,
		    #             n_days=DAYS,
		    #             all_players=players,
		    #             captain=True,
		    #             rfactor=True)
			sp = League(
					fantateams=self.fantateams,
					schedule=a_schedule,
					n_days=self.n_days,
					use_rfactor=True,
					use_captain=True
			)
			display(sp.create_ranking(double_check=False))
			display(df.style.set_properties(**{'width': '50px'}))


def get_points(team_name: str, day: int, use_rfactor: bool,
               use_captain: bool) -> (float, float, float):

	abs_points = dbf.db_select(
			table='absolute_points',
			columns=[f'day_{day}'],
			where=f'team_name = "{team_name}"'
	)[0]

	if not use_rfactor:
		r_points = 0.
	else:
		r_points = dbf.db_select(
				table='rfactor_points',
				columns=[f'day_{day}'],
				where=f'team_name = "{team_name}"'
		)[0]

	if not use_captain:
		c_points = 0.
	else:
		c_points = dbf.db_select(
				table='captain_points',
				columns=[f'day_{day}'],
				where=f'team_name = "{team_name}"'
		)[0]

	return abs_points, r_points, c_points


def assert_df_is_correct(computed_ranking: pd.DataFrame):

	"""
	Check if code is working correctly by comparing the result with the real
	data in the database.
	"""

	real_ranking = dbf.db_select(table='classifica', columns=['*'], where='')
	real_ranking = {team[0]: team[1:] for team in real_ranking}
	real_ranking = pd.DataFrame.from_dict(
			real_ranking,
			orient='index',
			columns=computed_ranking.columns
	)

	real_ranking_sorted = real_ranking.sort_index()
	computed_ranking_sorted = computed_ranking.sort_index()

	if not computed_ranking_sorted.equals(real_ranking_sorted):
		computed_ranking.sort_values('Pt', inplace=True, ascending=False)
		display(computed_ranking)
		print('Classifica reale:')
		display(real_ranking)
		raise ValueError('La classifica non coincide con quella reale')


def generate_points_dict(fantateams: [str], n_days: int) -> dict:
	return {ft: [sum(get_points(
			team_name=ft,
			day=d,
			use_rfactor=True,
			use_captain=True
	)) for d in range(1, n_days + 1)] for ft in fantateams}


def average_global_std(
		fantateams: [str],
		n_days: int,
		n_leagues: int,
		iterations: int) -> np.array:

	"""
	Compute the average std in the final positions (in %) of each team after
	running several random leagues multiple times.
	The lower the std the more reliable the result to be representative of the
	global behaviour.
	"""

	avg_std = {ft: [] for ft in fantateams}

	for i in range(iterations):
		cl = Calendar(
				fantateams=fantateams,
				n_leagues=n_leagues,
				n_days=n_days
		)
		positions = cl.positions

		for ft in fantateams:
			res = []
			for pos in positions:
				res.append(positions[pos][ft])
			avg_std[ft].append(res)

	avg_std = [np.mean(np.array(avg_std[ft]).std(axis=0)) for ft in avg_std]
	avg_std = np.mean(avg_std)

	return avg_std


def optimal_number_iterations(
		fantateams: [str],
		n_days: int):

	"""
	Run many random leagues in order to find out the number of random leagues
	needed to have stable and reproducible results.
	"""

	n_leagues_options = (
			[i for i in range(1, 11)] +
			[i for i in range(20, 101, 10)] +
			[i for i in range(250, 1001, 250)] +
			[i for i in range(2000, 10001, 2000)]
	)

	results = []
	for n_leagues in n_leagues_options:
		results.append(average_global_std(
				fantateams=fantateams,
				n_days=n_days,
				n_leagues=n_leagues,
				iterations=5
		))
		print(f'\r{n_leagues}', end='')

	fig, ax = plt.subplots(figsize=(9, 6))
	plt.plot(n_leagues_options, results, marker='o', c='r')
	ax.spines['right'].set_visible(False)
	ax.spines['top'].set_visible(False)
	plt.xlabel('Numero di campionati', fontsize=20)
	_ = plt.ylabel('Variabilità risultato', fontsize=20)
	plt.savefig('Loss_vs_n_leagues.png')
	plt.show()


DAYS = last_day_played()
print(f'Giornate disputate: {DAYS}')

teams = dbf.db_select(table='teams', columns=['team_name'], where='')

all_matches = [dbf.db_select(
		table='real_league',
		columns=[f'day_{i+1}'],
		where='') for i in range(DAYS)]

# lg = League(
# 		fantateams=teams,
# 		schedule=all_matches,
# 		n_days=DAYS,
# 		use_rfactor=True,
# 		use_captain=True
# )
# lg.create_ranking(double_check=True)
# cl = Calendar(fantateams=teams, n_leagues=100, n_days=DAYS)
# cl.specific_round(fantateam='FC 104', position=5)
