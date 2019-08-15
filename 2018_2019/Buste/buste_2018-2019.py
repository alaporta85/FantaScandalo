import os
import re
import pandas as pd
from tabulate import tabulate
from datetime import datetime
from Buste import db_functions as dbf
from Buste import extra_functions as ef

# dbase = '/Users/andrea/Desktop/Cartelle/Fantacalcio/2018-19/prova_db.db'
dbase = '/Users/andrea/Desktop/Cartelle/Bots/FantAstaBot/fanta_asta_db.db'


class Busta(object):

	def __init__(self, team):

		self.team = team

		# Players to buy, players to sell and additional money used for each
		# offer
		self.acquisti, self.cessioni, self.contanti = self.open_buste()

		# Players already sold. Used to handle different offers with same
		# players as payment: if they are used in one offer they cannot be
		# used in another one
		self.players_sold = []

		# Datetime of the email. Used only in case of two or more offers with
		# the same economical value
		self.dt = self.select_dt()

	def open_buste(self):

		"""
		Open the .txt file with all the offers of the fantateam and transform
		it into a dict like:

			{1: "CASTAN 5, ZAPATA C, 2",
			 2: "GIACCHERINI 4, LYANCO",
			 3: "CANCELO 6, 6",
			 4: "BURDISSO 6, 6",
			 5: ""
			 }

		Initialize the attributes "acquisti", "cessioni" and "contanti".

		Use the function fix_players_names() for the final result.

		:return: dict

		"""

		# Get the content of the document
		try:
			f = open('txt/{}.txt'.format(self.team))
			content = f.readlines()
			f.close()
		except FileNotFoundError:
			return [], [], []

		# Clean it a bit and append empty strings until it has 5 elements.
		# Appending '' instead of False or None is useful when we print the
		# results at the end
		content = [i.replace(' ', '').replace('\n', '') for i in content]
		while len(content) < 5:
			# noinspection PyTypeChecker
			content.append('')

		content = {i + 1: content[i] for i in range(5)}

		return fix_players_names(content)

	def select_dt(self):

		"""
		Select the datatime of the email, i.e. date and time when the email
		with the .txt has been received. It is used to sort the offers: when
		2 users offer the same amount of money for a player, the one who sent
		the email first win.

		Used to initialize the attribute "dt".

		:return: datetime

		"""

		dt = dbf.db_select(database=dbase,
		                   table='buste',
		                   columns_in='busta_dt',
		                   where='busta_team = "{}"'.format(self.team))[0]
		if not dt:
			dt = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

		return datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')


def budget_is_ok(tm, players_to_sell, price):

	"""
	Check whether the team has money to pay the price and buy the player.
	Used inside buste_results().

	:param tm: str, fantateam
	:param players_to_sell: list, players sold and used to pay the price.
							Ex. ['MESSI', 'MARADONA']
	:param price: int, value of the offer

	:return: int if budget is enough, False otherwise

	"""

	budg = budgets[tm]

	for player in players_to_sell:

		budg += dbf.db_select(
				database=dbase,
				table='players',
				columns_in=['player_price'],
				where='player_name = "{}"'.format(player))[0]

	return budg if price <= budg else False


def buste_results():

	"""
	Assign all the players following the rules.

	:return: dict, results

	"""

	results = {i: [] for i in budgets}

	for i in range(1, 6):

		# Assign players until all players in the i-th slot are assigned
		while True:

			# Select all i-th offers
			offers = [(nm, buste[nm].acquisti[i], buste[nm].dt) for nm in
			          budgets if buste[nm].acquisti[i]]

			if not offers:
				break

			# Sort them by datetime and value of the offer. This means that it
			# will be always selected the most expensive player. In case of 2
			# or more offers with the same value, player will be assigned to
			# who sent the email first
			offers.sort(key=lambda x: x[2])
			offers.sort(key=lambda x: x[1][1], reverse=True)

			team, offer, _ = offers[0]
			player, price = offer
			players_to_sell = buste[team].cessioni[i]

			# To correctly assign a player, we need to check that the players
			# used to pay (if any) have not been sold in previous offers and
			# that the budget is enough to cover the price
			if (players_are_available(team, players_to_sell) and
			   type(budget_is_ok(team, players_to_sell, price)) != bool):

				# Update budget of the fantateam who acquired the player
				budgets[team] = (budget_is_ok(
						team, players_to_sell, price) - price)

				# Update the number of players per team
				number_of_players_per_team[team] += (1 - len(players_to_sell))

				# Set its i-th entry to be False
				buste[team].acquisti[i] = False

				# Update results
				results[team].append('{}, {}'.format(player, price))

				# Update the offers of the remaining fantateams. Basically we
				# delete the offers relative to this player and shift all the
				# rest up
				offer_is_lost(i, player,
				              all_teams=[i for i in budgets if i != team])
			else:

				# In case the fantateam is not able to pay the player, we
				# update its offers and shit them up
				offer_is_lost(i, player, all_teams=[team])

	# Append empty strings for nice printing
	for i in results:
		while len(results[i]) < 5:
			results[i].append('')

	return results


def extract_player_to_buy_and_price(player_to_buy):

	"""
	Take the player written in the .txt and correct its name if mispelled.
	Used inside fix_players_names().

	:param player_to_buy: str, Ex. "Sczezny20"

	:return: tuple, Ex. (SZCZESNY, 20)

	"""

	price = re.findall('\d+', player_to_buy)[0]
	player_to_buy = player_to_buy.replace(price, '').upper()

	player_to_buy = ef.jaccard_result(player_to_buy,
	                                  dbf.db_select(
			                                  database=dbase,
			                                  table='players',
			                                  columns_in=['player_name']), 3)

	return player_to_buy, int(price)


def extract_players_to_sell_and_cash(payment):

	"""
	Take the players written in the .txt and correct their name if mispelled.
	Also separe players to sell from the cash.
	Used inside fix_players_names().

	:param payment: list, Ex. [Gildias, 2]

	:return: tuple, Ex. ([GIL DIAS], 2)

	"""

	try:
		cash = re.findall('\d+', ''.join(payment))[0]
		players_to_sell = [i for i in payment if i != cash]
	except IndexError:
		cash = 0
		players_to_sell = payment

	for i in range(len(players_to_sell)):
		players_to_sell[i] = ef.jaccard_result(
				players_to_sell[i], dbf.db_select(
						database=dbase,
						table='players',
						columns_in=['player_name']), 3)

	return players_to_sell, cash


def fix_buste_names():

	"""
	Fix the name of the .txt file in case it doesn not match the exact name of
	the fantateam as it appears in the database.

	:return: nothing

	"""

	for filename in os.listdir('txt'):
		if filename.endswith('.txt'):
			correct_team = ef.jaccard_result(filename, budgets, 3)
			os.rename('txt/' + filename, 'txt/{}.txt'.format(correct_team))


def fix_players_names(offers):

	"""
	Fix the name of the players in all the offers in order to make them match
	with the database entries.
	Used inside open_buste().

	:param offers: dict, the original offers which have to be fixed. All spaces
				   are removed previously. Ex:

						{1: "messi60, bonaventua, 40",
						 2: "cristianoronaldo70, salah, 25",
						 3: "vieri50, 50",
						 4: "",
						 5: ""
						 }

	:return: 3 dict, representing players to buy, players to sell and cash.
			 For example, with the dict above the return will be:

			 acquisti = {1: (MESSI, 60),
			             2: (CRISTIANO RONALDO, 70),
			             3: (VIERI, 50),
			             4: False,
			             5: False
			             }

			 cessioni = {1: [BONAVENTURA],
			             2: [SALAH],
			             3: [],
			             4: False,
			             5: False
			             }

			 contanti = {1: 40,
			             2: 25,
			             3: 50,
			             4: False,
			             5: False
			             }
	"""

	acquisti, cessioni, contanti = {}, {}, {}

	for of in offers:

		# If there is not offer in this position than just add False and go on
		if not offers[of]:
			acquisti[of] = False
			cessioni[of] = False
			contanti[of] = False
			continue

		# Separe all the elements of the offer
		data = offers[of].split(',')

		# Separe the player to buy from all the rest
		player_to_buy, payment = data[0], data[1:]

		# Modify the three dicts with the correct names
		acquisti[of] = extract_player_to_buy_and_price(player_to_buy)
		cessioni[of], contanti[of] = extract_players_to_sell_and_cash(payment)

	return acquisti, cessioni, contanti


def get_number_of_players():

	teams = dbf.db_select(
			database=dbase,
			table='teams',
			columns_in=['team_name'])

	res = {i: 0 for i in teams}
	for team in res:
		players = dbf.db_select(
				database=dbase,
				table='players',
				columns_in=['player_id'],
				where='player_status = "{}"'.format(team))
		res[team] = len(players)

	return res


def offer_is_lost(slot, player, all_teams):

	"""
	When a player is acquired by any team, this function modifies the dicts
	containing all the other teams' offers. In details, all the other dicts
	containing the player just acquired will be shifted up in order to respect
	the order of priorities. For example, if DZEMAILI is acquired by Ciolle
	United than the original offers of fcpastaboy

			{1: (DZEMAILI, 35),
			 2: (DE MAIO, 8),
			 3: (BABACAR, 30),
			 4: (RICCI, 5),
			 5: (CODA M, 8)}

	will be modified into

			{1: (DE MAIO, 8),
			 2: (BABACAR, 30),
			 3: (RICCI, 5),
			 4: (CODA M, 8),
			 5: False}

	This operates on the three dicts acquisti, cessioni and contanti.
	Used inside buste_results().

	:param slot: int, slot of the offer
	:param player: str, player just acquired
	:param all_teams: list, all the fantateams whose offers need to be checked
					  and eventually modified

	:return: nothing

	"""

	for tm in all_teams:

		# Start from 'slot' because previous offers must not be modified
		for i in range(slot, 6):

			# If there in no offer in the slot or it is for a different player
			# we go to the next one
			if not buste[tm].acquisti[i] or buste[tm].acquisti[i][0] != player:
				continue
			else:

				# Otherwise we modify all the enties by shifting them up
				for j in range(i, 6):
					try:
						buste[tm].acquisti[j] = buste[tm].acquisti[j + 1]
						buste[tm].cessioni[j] = buste[tm].cessioni[j + 1]
						buste[tm].contanti[j] = buste[tm].contanti[j + 1]
					except KeyError:
						buste[tm].acquisti[j] = False
						buste[tm].cessioni[j] = False
						buste[tm].contanti[j] = False

				break


def players_are_available(tm, players_to_sell):

	"""
	Check whether the players used as payment have already been sold in a
	previous offer. If not than return True and add them to the list of sold
	players, else False.
	Used inside buste_results().

	:param tm: str, name of fantateam
	:param players_to_sell: list, Ex. [VERDI, INSIGNE]

	:return: bool

	"""

	check = set(players_to_sell) & set(buste[tm].players_sold) == set()

	if check:
		for player in players_to_sell:
			buste[tm].players_sold.append(player)

	return check


def print_original(tm):

	"""
	Extract the raw content of each .txt for printing.
	Used inside print_results().

	:param tm: str, fantateam

	:return: list, all the offers as written in the .txt

	"""

	try:
		f = open('txt/{}.txt'.format(tm))
		content = f.readlines()
		f.close()
	except FileNotFoundError:
		return ''

	content = [i.replace('\n', '') for i in content]
	while len(content) < 5:
		# noinspection PyTypeChecker
		content.append('')

	return content


def print_results():

	"""
	Print the final results.

	:return: nothing

	"""

	group1 = ['Atletico cu tri Arancini', 'Bucalina', 'Ac Picchia', 'Fc Roxy']
	group2 = ['fcpastaboy', 'Ciolle United', 'FC STRESS', 'FC BOMBAGALLO']

	original1 = tabulate(pd.DataFrame({i: print_original(i) for i in group1}),
	                     showindex=False, headers='keys', tablefmt="orgtbl")
	original2 = tabulate(pd.DataFrame({i: print_original(i) for i in group2}),
	                     showindex=False, headers='keys', tablefmt="orgtbl")
	risultati = tabulate(pd.DataFrame(buste_results()), showindex=False,
	                     headers='keys', stralign='right', tablefmt="orgtbl")

	buchi = {i: MIN_NUM_PLAYERS - number_of_players_per_team[i] for i in
	         budgets}
	buchi = {i: buchi[i] if buchi[i] > 0 else 0 for i in buchi}
	info = {i: '{} ({})'.format(budgets[i], buchi[i]) for i in buchi}
	info = tabulate(pd.DataFrame(info, index=[0]), showindex=False,
	                headers='keys', numalign='center', tablefmt="orgtbl")

	print('\n{}\n\nBUSTE ORIGINALI\n'.format('- ' * 80))
	print(original1 + '\n')
	print(original2)
	print('\n{}\n\nESITO BUSTE\n'.format('- ' * 80))
	print(risultati)
	print('\n{}\n\nSOLDI RIMANENTI (BUCHI)\n'.format('- ' * 80))
	print(info)


MIN_NUM_PLAYERS = 25
EXTRA_MONEY = 20

number_of_players_per_team = get_number_of_players()

budgets = dbf.db_select(
		database=dbase,
		table='budgets',
		columns_in=['budget_team', 'budget_value'])
budgets = {el[0]: el[1] + EXTRA_MONEY for el in budgets}

print('\nBUDGET INIZIALE\n')
print(tabulate(pd.DataFrame(budgets, index=[0]), showindex=False,
               headers='keys', numalign='center', tablefmt="orgtbl"))


fix_buste_names()

buste = {i: Busta(i) for i in budgets}

print_results()
