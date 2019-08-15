import os
import random
import string
import db_functions as dbf
from itertools import combinations, zip_longest

ALL_LEAGUES = ('/Users/andrea/Desktop/Cartelle/Bots/FantaScandaloBot/'
               'All_Leagues_8teams.txt')


def generate_schedule(a_round, days):

	"""
	Returns a list which represents the complete schedule, created by the
	input a_round and containing 'days' days.

	"""

	complete_rounds = days // len(a_round)
	rest = days % len(a_round)

	return a_round * complete_rounds + a_round[:rest]


def clean_round(a_round):

	"""
    Takes a string as input which has the form:

	[(('A','B'),('C','D'),('E','F'),('G','H')),(('A','C'),.......]

    and returns it clean as:

	ABCDEFGHAC..........

    Such string will be then written in the .txt file inside the function
    all_leagues_generator_txt(teams).

	"""

	return ''.join([''.join(match) for day in a_round for match in day])


def no_repeated_teams(day, teams):

	"""
    Checks whether a team appears more than once in one day. If not, the day
    is a valid one and returns True, else False.

	"""

	res = [team for match in day for team in match]
	if len(set(res)) == len(teams):
		return True
	else:
		return False


def available_days(day, all_days, teams):

	"""
	Returns the list of the days which are available in the round where the
	day "day" is already present. This is to avoid that any match can be
	played more than once in one round.

	"""

	res = []
	for new_day in all_days:
		comb = day + new_day
		if len(set(comb)) == len(teams):
			res.append(new_day)

	return res


def all_leagues_generator_txt(n_teams):

	"""
	Generates a .txt file containing all the possible rounds considering
	the input 'teams'. Each line in the file is a complete round. In our
	case we generate it by using letters as team names. Since there are 8
	teams, each round has:

    	   - 7 days
    	   - 4 matches per day
    	   - 2 teams per match

	So each line in our file will have 56 letters, each letter representing
	one of the real fantateams. The transformation from letters to real team
	will be done later by using the function real_round_from_line.

	"""

	def recursive_rounds(round_to_fill, only_valid_days):

		"""
		Writes recursively the rounds in the file.

		"""

		for valid_day in only_valid_days:
			round_copy = round_to_fill.copy()
			round_copy.append(valid_day)

			if len(round_copy) == len(teams) - 1:
				cleaned_round = str(clean_round(round_copy))
				myfile.write(cleaned_round + '\n')
			else:
				new_list = available_days(valid_day, only_valid_days, teams)
				recursive_rounds(round_copy, new_list)

	teams = [string.ascii_uppercase[i] for i in range(n_teams)]

	# All the possible matches
	pairs = list(combinations(teams, 2))

	n_matches_per_day = len(teams) // 2

	# All the possible days
	all_days = combinations(pairs, n_matches_per_day)

	# # If there are NO repeated teams in all the matches forming a day, it means
	# # it is a valid day
	all_valid_days = [day for day in all_days if no_repeated_teams(day, teams)]

	a_round = []
	myfile = open(ALL_LEAGUES, 'w')
	recursive_rounds(a_round, all_valid_days)
	myfile.close()


def get_random_line(filename):

	"""
	Returns the content of a random line inside a .txt file.

	"""

	# First extract the number of bytes of the file
	total_bytes = os.stat(filename).st_size

	# Then we select a random point in the file by selecting a random byte
	random_point = random.randint(0, total_bytes)

	# Open the file
	myfile = open(filename)

	# Go to the randomly selected point
	myfile.seek(random_point)

	# Skip this line to clear the partial line
	myfile.readline()

	# Assing the content of the next complete line to a variable and close the
	# file
	line = myfile.readline()
	myfile.close()

	# Returns everything except the last carachter of the string which is '\n'
	return line[:-1]


def real_round_from_line(line):

	"""
	Takes the input which is a random line from the .txt file and has the
	form:

    	   ABCDEFGHAC..........

	and transforms it into a complete round with the real names of the
	fantateams by using the dict 'letters'.

	"""

	def grouper(iterable, n, fillvalue=None):
		args = [iter(iterable)] * n
		return zip_longest(*args, fillvalue=fillvalue)

	fantateams = dbf.db_select(table='teams', columns=['team_name'])
	letters = string.ascii_uppercase

	letter2team = {letters[i]: fantateams[i] for i in range(len(fantateams))}

	final_round = [letter2team[i] for i in list(line)]
	final_round = grouper(final_round, 2)

	return list(grouper(final_round, len(letter2team) // 2))


def random_rounds(number):

	"""
	Returns a list of 'number' random rounds ready to be used in the
	simulation. Each of these rounds will be used later to generate a
	complete schedule by using the function generate_schedule(a_round,
	total_days).

	"""

	res = []
	for x in range(number):
		line = get_random_line(ALL_LEAGUES)
		real_round = real_round_from_line(line)
		res.append(real_round)

	return res
