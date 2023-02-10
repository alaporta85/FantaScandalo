import os
import re
import pickle
import pandas as pd
from tabulate import tabulate
from typing import List, Tuple, Dict

import db_functions as dbf
# import utils as ef
import logging_file as log


class Busta(object):

	def __init__(self, fantateam: str):

		self.fantateam = fantateam
		self.n_players = self.get_number_of_players()
		self.raw_content = self.get_raw_content()
		self.initial_budget = self.get_budget() + EXTRA_MONEY
		self.budget = self.get_budget() + EXTRA_MONEY
		self.pos = [i[0] for i in RANKING].index(self.fantateam) + 1
		self.abs_points = RANKING[self.pos - 1][1]

		# Players to buy, players to sell and additional money used for each
		# offer
		self.acquisti, self.cessioni, self.contanti = self.open_buste()

		# Players already sold. Used to handle different offers with same
		# players as payment: if they are used in one offer they cannot be
		# used in another one
		self.players_sold = []

		# Used to get initial priorities
		self.only_names = [
			self.acquisti[i][0] for i in self.acquisti if self.acquisti[i]
		]

	def get_number_of_players(self) -> int:
		players = dbf.db_select(
				database=DBASE1,
				table='players',
				columns_in=['player_id', 'player_status'],
				where=f'player_status = "{self.fantateam}"'
		)
		return len(players)

	def get_budget(self) -> int:
		return dbf.db_select(
				database=DBASE1,
				table='budgets',
				columns_in=['budget_value'],
				where=f'budget_team="{self.fantateam}"'
		)[0]

	def get_raw_content(self) -> List[str]:

		with open(f'txt/{self.fantateam}.txt', 'r') as file:
			content = file.readlines()
		content = [i.replace('\n', '') for i in content]

		while len(content) < MAX_NUM_OFFERS:
			content.append('')
		return content

	def open_buste(self) -> Tuple[
		Dict[int, Tuple[str, int]],
		Dict[int, Tuple[str]],
		Dict[int, int]
	]:

		# Clean it a bit and append empty strings until it has all elements.
		# Appending '' instead of False or None is useful when we print the
		# results at the end
		offers = [offer.replace(' ', '') for offer in self.raw_content]
		while len(offers) < MAX_NUM_OFFERS:
			offers.append('')
		offers = {i+1: offers[i] for i in range(MAX_NUM_OFFERS)}

		acquisti, cessioni, contanti = {}, {}, {}
		for idx in offers:
			# If there is not offer in this position than just add False and go on
			if not offers[idx]:
				acquisti[idx] = tuple()
				cessioni[idx] = tuple()
				contanti[idx] = 0
				continue

			# Separe all the elements of the offer
			data = offers[idx].split(',')

			# Separe the player to buy from all the rest
			player_to_buy, payment = data[0], data[1:]

			# Modify the three dicts with the correct names
			acquisti[idx] = extract_player_to_buy_and_price(
					player_to_buy=player_to_buy
			)
			cessioni[idx], contanti[idx] = extract_players_to_sell_and_cash(
					fantateam=self.fantateam,
					payment=payment
			)

		return acquisti, cessioni, contanti


def get_fantateams() -> List[str]:
	return [name for name, _ in RANKING]


def get_ranking():
	return dbf.db_select(
			database=DBASE2,
			table='classifica',
			columns_in=['team', 'Tot']
	)


def compute_budget_after_selling(
		fantateam_busta: Busta,
		players_to_sell: Tuple[str],
) -> int:

	# Load fantateam's budget
	budget_after = fantateam_busta.budget

	# Add values of players ready to be sold
	for player in players_to_sell:
		budget_after += dbf.db_select(
				database=DBASE1,
				table='players',
				columns_in=['player_price'],
				where=f'player_name = "{player}"'
		)[0]
	return budget_after


def budget_is_enough(
		fantateam_busta: Busta,
		player_name: str,
		players_to_sell: Tuple[str],
		price: int
) -> bool:

	budget_after = compute_budget_after_selling(
			fantateam_busta=fantateam_busta,
			players_to_sell=players_to_sell
	)

	# Return budget if enough else 0
	if price <= budget_after:
		return True
	else:
		LOGGER.info(f"Offerta non sufficiente: "
		            f"{fantateam_busta.fantateam} perde {player_name}")
		return False


def get_winning_offer(
		all_offers: List[Tuple[str, str, int, int, float, int]]
) -> Tuple[str, str, int]:
	# The winning offer is:
	#   - The offer with the highest value
	#   - If tie, the offer with the INITIAL highest priority
	#   - If tie, the offer of the team with the highest absolute points
	#   - If tie, the offer of the team with the highest ranking position
	all_offers.sort(key=lambda x: x[5])
	all_offers.sort(key=lambda x: x[4], reverse=True)
	all_offers.sort(key=lambda x: x[3])
	all_offers.sort(key=lambda x: x[2], reverse=True)

	# Only fantateams and offer are needed, rest of data is for sorting
	return all_offers[0][:3]


def buste_results(original_buste: Dict[str, Busta]) -> dict:

	final_dict = {i: [] for i in FANTATEAMS}
	for i in range(1, MAX_NUM_OFFERS+1):

		# Assign players until all players in the i-th slot are assigned
		while True:
			# Select all i-th offers
			offers = [
				(
					nm,
					buste[nm].acquisti[i][0],
					buste[nm].acquisti[i][1],
					buste[nm].only_names.index(buste[nm].acquisti[i][0]),
					buste[nm].abs_points,
					buste[nm].pos
				) for nm in final_dict if original_buste[nm].acquisti[i]
			]
			if not offers:
				break

			# Select winning offer and corresponding busta
			fteam, player, price = get_winning_offer(all_offers=offers)
			busta = original_buste[fteam]
			players_to_sell = busta.cessioni[i]

			# To correctly assign a player, we need to check that
			#   - budget is enough
			#   - final number of players does not exceed limit
			#   - players used to pay (if any) are still available
			if (
					budget_is_enough(busta, player, players_to_sell, price) and
					players_dont_exceed(busta, player, players_to_sell) and
					players_are_available(busta, player, players_to_sell)
			):

				# Update players sold
				busta.players_sold += players_to_sell

				# Update budget of the fantateam who acquired the player
				new_budget = compute_budget_after_selling(
						fantateam_busta=busta,
						players_to_sell=players_to_sell) - price
				busta.budget = new_budget

				# Update the number of players per team
				busta.n_players += (1 - len(players_to_sell))

				# Set its i-th entry to be False
				busta.acquisti[i] = tuple()

				# Update results
				final_dict[fteam].append(f'{player}, {price}')

				# Update the offers of the remaining fantateams. Basically we
				# delete the offers relative to this player and shift all the
				# rest up
				offer_is_lost(
						player_name=player,
						losing_fteams=[i for i in FANTATEAMS if i != fteam]
				)

				if MODIFY_DB:
					update_db(
							fantateam=fteam,
							new_budget=new_budget,
							player_name=player,
							players_to_sell=players_to_sell
					)
			else:
				# print(f'{team} not able to pay for {player}')
				# In case the fantateam is not able to pay the player, we
				# update its offers and shit them up
				offer_is_lost(player_name=player, losing_fteams=[fteam])

	# Append empty strings for nice printing
	for i in final_dict:
		while len(final_dict[i]) < MAX_NUM_OFFERS:
			final_dict[i].append('')

	return final_dict


def extract_player_to_buy_and_price(player_to_buy: str) -> Tuple[str, int]:

	# Separate name from price
	name = re.findall(r'[a-zA-Z]+', player_to_buy)[0]
	price = re.findall(r'\d+', player_to_buy)[0]

	# Get all FREE players from db
	all_free_players = dbf.db_select(
			database=DBASE1,
			table='players',
			columns_in=['player_name'],
			where='player_status = "FREE"'
	)

	# Fix the input
	name = ef.jaccard_result(
			input_option=name,
			all_options=all_free_players,
			ngrm=3
	)

	return name, int(price)


def extract_players_to_sell_and_cash(
		fantateam: str,
		payment: List[str]
) -> Tuple[Tuple[str], int]:

	# Get all fantateam's players
	all_players = dbf.db_select(
			database=DBASE1,
			table='players',
			columns_in=['player_name'],
			where=f'player_status = "{fantateam}"'
	)

	# In the payment, separate players from cash
	try:
		cash = re.findall(r'\d+', ''.join(payment))[0]
		players_to_sell = [i for i in payment if i != cash]
	except IndexError:
		cash = '0'
		players_to_sell = payment

	# Fix names
	for i, name in enumerate(players_to_sell):
		players_to_sell[i] = ef.jaccard_result(
				input_option=name,
				all_options=all_players,
				ngrm=3
		)

	return tuple(players_to_sell), int(cash)


def fix_buste_names() -> None:

	# Wrong names
	filenames = [file for file in os.listdir('txt') if file.endswith('.txt')]
	names = map(lambda x: x.split('.')[0], filenames)

	# Fix
	for wrong_name in names:
		correct_team = ef.jaccard_result(
				input_option=wrong_name,
				all_options=FANTATEAMS,
				ngrm=3
		)
		old_path = os.path.join('txt', f'{wrong_name}.txt')
		new_path = os.path.join('txt', f'{correct_team}.txt')
		os.rename(old_path, new_path)


def get_number_of_players() -> Dict[str, int]:
	players = dbf.db_select(
			database=DBASE1,
			table='players',
			columns_in=['player_id', 'player_status'],
			where='player_status != "FREE"'
	)
	players = [name for _, name in players]
	return pd.Series(players).value_counts().to_dict()


def shift_list_up(index: int, dict_to_shift: dict) -> dict:

	values = list(dict_to_shift.values())
	values[index:] = values[index + 1:]
	values.append(False)
	return {slot: value for slot, value in enumerate(values, 1)}


def offer_is_lost(player_name: str, losing_fteams: list) -> None:

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
	"""

	for fteam in losing_fteams:

		# Loaded every time since it is updated at every iteration
		updated_slots = [
			i[0] if i else i for i in buste[fteam].acquisti.values()
		]

		# No need to shift if player not in offers
		if player_name not in updated_slots:
			continue

		# Identify position of the player inside list of offers
		idx = updated_slots.index(player_name)

		# Update all attributes
		buste[fteam].acquisti = shift_list_up(
				index=idx, dict_to_shift=buste[fteam].acquisti
		)

		buste[fteam].cessioni = shift_list_up(
				index=idx, dict_to_shift=buste[fteam].cessioni
		)

		buste[fteam].contanti = shift_list_up(
				index=idx, dict_to_shift=buste[fteam].contanti
		)


def players_are_available(
		fantateam_busta: Busta,
		player_name: str,
		players_to_sell: Tuple[str]
) -> bool:

	"""
	Check whether the players used as payment have already been sold in a
	previous offer. If not than return True and add them to the list of sold
	players, else False.
	"""

	check = set(players_to_sell) & set(fantateam_busta.players_sold) == set()

	if check:
		return True
	else:
		LOGGER.info(f"Pagamento non più valido: "
		            f"{fantateam_busta.fantateam} perde {player_name}")
		pass

	return check


def players_dont_exceed(
		fantateam_busta: Busta,
		player_name: str,
		players_to_sell: Tuple[str]
) -> bool:

	players_to_add = 1 - len(players_to_sell)
	if fantateam_busta.n_players + players_to_add <= MAX_NUM_PLAYERS:
		return True
	else:
		LOGGER.info(f"Troppi giocatori in rosa: "
		            f"{fantateam_busta.fantateam} perde {player_name}")
		return False


def print_results(
		original_buste: Dict[str, Busta],
		data_to_print: Dict[str, List[str]]
) -> None:

	# Budgets before buste
	budgets_dict = {
		fteam: original_buste[fteam].initial_budget for fteam in data_to_print}
	print('\nBUDGETS INIZIALI')
	print(tabulate(pd.DataFrame(budgets_dict, index=[0]), showindex=False,
	               headers='keys', numalign='center', tablefmt="orgtbl"))

	# Create groups
	n_fteams = len(FANTATEAMS) // 2
	group1 = FANTATEAMS[:n_fteams]
	group2 = FANTATEAMS[n_fteams:]

	original1 = pd.DataFrame(
			{fteam: original_buste[fteam].raw_content for fteam in group1})
	original1 = tabulate(
			tabular_data=original1,
			showindex=False,
			headers='keys',
			tablefmt="orgtbl"
	)

	original2 = pd.DataFrame(
			{fteam: original_buste[fteam].raw_content for fteam in group2})
	original2 = tabulate(
			tabular_data=original2,
			showindex=False,
			headers='keys',
			tablefmt="orgtbl"
	)
	print(f'\n{"- " * 80}\n\nBUSTE ORIGINALI')
	print(f'{original1}\n\n{original2}')

	data = tabulate(
			tabular_data=pd.DataFrame(data_to_print),
			showindex=False,
			headers='keys',
			stralign='right',
			tablefmt="orgtbl"
	)
	print(f'{"- " * 80}\n\nESITO BUSTE')
	print(data)

	buchi = {
		fteam: MIN_NUM_PLAYERS - original_buste[fteam].n_players
		for fteam in original_buste
	}
	buchi = {fteam: buchi[fteam] if buchi[fteam] > 0 else 0 for fteam in buchi}
	info = {
		fteam: f'{original_buste[fteam].budget} ({buchi[fteam]})'
		for fteam in buchi
	}
	info = tabulate(
			tabular_data=pd.DataFrame(info, index=[0]),
			showindex=False,
			headers='keys',
			numalign='center',
			tablefmt="orgtbl"
	)
	print(f'{"- " * 80}\n\nBUDGETS FINALI (BUCHI)')
	print(info)


def update_db(
		fantateam: str,
		new_budget: int,
		player_name: str,
		players_to_sell: Tuple[str]
) -> None:

	# Update status of acquired player
	dbf.db_update(
			database=DBASE1,
			table='players',
			columns=['player_status'],
			values=[fantateam],
			where=f'player_name = "{player_name}"'
	)

	# Update status of sold players
	for player in players_to_sell:
		dbf.db_update(
				database=DBASE1,
				table='players',
				columns=['player_status'],
				values=['FREE'],
				where=f'player_name = "{player}"'
		)

	# Update fantateam's budget
	dbf.db_update(
			database=DBASE1,
			table='budgets',
			columns=['budget_value'],
			values=[new_budget],
			where=f'budget_team = "{fantateam}"'
	)

	# TODO update stats in DBASE2


# Log
LOGGER = log.set_logging()

# Set paths
MAIN_DIR = '/Users/andrea/Desktop/Cartelle/Bots'
DBASE1 = f'{MAIN_DIR}/FantAstaBot/fanta_asta_db.db'
DBASE2 = f'{MAIN_DIR}/FantaScandalo/fantascandalo_db.db'

# Set constants
MIN_NUM_PLAYERS = 25
MAX_NUM_PLAYERS = 32
EXTRA_MONEY = 20
MAX_NUM_OFFERS = 5
MODIFY_DB = False
RANKING = get_ranking()
FANTATEAMS = get_fantateams()

# Fix filenames
fix_buste_names()

# Open all buste
buste = {i: Busta(i) for i in FANTATEAMS}

# Distribute players
results = buste_results(original_buste=buste)

print_results(original_buste=buste, data_to_print=results)

with open('refer.pickle', 'rb') as f:
	b = pickle.load(f)
assert results == b
