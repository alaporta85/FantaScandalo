import os
import time
import db_functions as dbf
import config as cfg
import pandas as pd
from openpyxl import load_workbook
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.by import By
from selenium import webdriver


def find_matches(brow: webdriver) -> (list, bool):
	matches_path = './/div[contains(@class, "match-details card calculated")]'
	return brow.find_elements_by_xpath(matches_path)


def format_player_name(player_name: str) -> str:
	return player_name.strip().upper().replace('.', '').replace(' *', '')


def get_team_name(brow: webdriver, match_header: webdriver) -> str:
	scroll_to_element(brow=brow, element=match_header)
	return match_header.text.split('\n')[0]


def get_points(brow: webdriver, match_table: webdriver) -> (float, float):
	scroll_to_element(brow=brow, element=match_table)
	data = match_table.text.split('ALTRI PUNTI\n')[1].split('\n')

	if 'Modificatore Rendimento' in data:
		idx = data.index('Modificatore Rendimento') + 1
		r_points = float(data[idx])
	else:
		r_points = 0.

	if 'Bonus Capitano' in data:
		idx = data.index('Bonus Capitano') + 1
		c_points = float(data[idx])
	else:
		c_points = 0.

	return r_points, c_points, float(data[-2])


def last_day_played() -> int:

	"""
	Return last day which has been played. Last day played is defined as the
	last day in the db where absolute points are saved.
	"""

	list_of_abs_points = dbf.db_select(table='absolute_points',
	                                   columns=['*'],
	                                   where='')[0][1:]

	try:
		return list_of_abs_points.index(None)
	except ValueError:
		# Updating after the last day of the league will give a ValueError
		return len(list_of_abs_points)


def open_excel_file(filename: str) -> pd.DataFrame:

	"""
	Try opening the file until found.
	"""

	while True:

		try:
			wb = load_workbook(filename)
			ws = wb.active

			players = pd.DataFrame(ws.values)
			players.columns = players.iloc[1]
			players = players.iloc[2:].copy()
			players.reset_index(drop=True, inplace=True)

			return players
		except FileNotFoundError:
			continue


def manage_adblock() -> webdriver:

	"""
	Start the browser with adblock.
	"""

	# Use AdBlock
	chop = webdriver.ChromeOptions()
	chop.add_extension('AdBlock_v3.34.0.crx')
	chop.add_argument("--disable-infobars")
	brow = webdriver.Chrome(cfg.CHROME_PATH, chrome_options=chop)
	time.sleep(10)

	handles = brow.window_handles
	brow.switch_to.window(handles[1])
	brow.close()
	brow.switch_to.window(handles[0])

	return brow


def activate_scrolling(brow: webdriver, element: webdriver or None,
                       activation_path: str) -> None:

	if not element:
		some_element = brow.find_element_by_xpath(activation_path)
	else:
		some_element = element.find_element_by_xpath(activation_path)
	time.sleep(1)
	scroll_to_element(brow=brow, element=some_element)
	time.sleep(1)


def extract_and_store_points(brow: webdriver, match_table: webdriver,
                             which_day: int, which_team: str) -> str:

	path = f'.//div[contains(@class, "{which_team}")]'
	header, table = match_table.find_elements_by_xpath(path)
	team_name = get_team_name(brow=brow, match_header=header)
	r_points, c_points, tot_points = get_points(
			brow=brow,
			match_table=table
	)

	dbf.db_update(
			table='rfactor_points',
			columns=[f'day_{which_day}'],
			values=[r_points],
			where=f'team_name = "{team_name}"'
	)

	dbf.db_update(
			table='captain_points',
			columns=[f'day_{which_day}'],
			values=[c_points],
			where=f'team_name = "{team_name}"'
	)

	dbf.db_update(
			table='absolute_points',
			columns=[f'day_{which_day}'],
			values=[tot_points - r_points - c_points],
			where=f'team_name = "{team_name}"'
	)

	return team_name


def scrape_lineups_schemes_points(brow: webdriver) -> webdriver:

	starting_day = last_day_played() + 1
	for day in range(starting_day, cfg.N_DAYS+1):

		brow.get(f'{cfg.FANTASCANDALO_URL}formazioni/{day}')

		if no_more_days_to_scrape(brow=brow, day_to_scrape=day):
			return brow

		# To activate scrolling
		activ_path = './/h4[@class="has-select clearfix flex"]'
		activate_scrolling(brow=brow, element=None, activation_path=activ_path)

		# Find all matches
		matches = find_matches(brow=brow)

		# Update database
		for i, match in enumerate(matches, 1):

			home_team = extract_and_store_points(
					brow=brow,
					match_table=match,
					which_day=day,
					which_team='home'
			)

			away_team = extract_and_store_points(
					brow=brow,
					match_table=match,
					which_day=day,
					which_team='away'
			)

			dbf.db_update(
					table='real_league',
					columns=[f'day_{day}'],
					values=[f'{home_team} - {away_team}'],
					where=f'match_id = {i}'
			)

			# To activate scrolling
			activ_path = './/button[contains(@class, "share-facebook")]'
			activate_scrolling(
					brow=brow,
					element=match,
					activation_path=activ_path
			)

	return brow


def scrape_classifica(brow: webdriver) -> None:

	brow.get(f'{cfg.FANTASCANDALO_URL}classifica')
	time.sleep(3)

	dbf.empty_table(table='classifica')

	positions = brow.find_elements_by_xpath(
			'.//table[contains(@class, "table-striped")]/tbody/tr')

	columns = ['team', 'G', 'V', 'N', 'P', 'Gf', 'Gs', 'Dr', 'Pt', 'Tot']
	for pos in positions:
		team_data = []
		scroll_to_element(brow, pos)
		fields = pos.find_elements_by_xpath('.//td')[2:-2]

		for field in fields:
			team_data.append(field.text)

		dbf.db_insert(table='classifica',
		              columns=columns,
		              values=team_data)


def regular_or_from_bench(player: webdriver) -> (int, int, int):

	"""
	Set info about playing and substitutions for each player.

	:param player: selenium element

	:return: tuple, (int, int, int)

	"""

	in_out = player.find_elements_by_xpath('.//img')
	attrs = [i.get_attribute('title') for i in in_out]

	regular = 0
	going_in = 0
	going_out = 0
	if 'Subentrato' not in attrs and 'Sostituito' not in attrs:
		regular += 1
	elif 'Subentrato' in attrs and 'Sostituito' not in attrs:
		going_in += 1
	elif 'Subentrato' not in attrs and 'Sostituito' in attrs:
		regular += 1
		going_out += 1
	elif 'Subentrato' in attrs and 'Sostituito' in attrs:
		going_in += 1
		going_out += 1

	return regular, going_in, going_out


def get_yellow_red_cards(player: webdriver) -> (int, int):

	# Select alvin element
	data = player.find_elements_by_xpath('.//div[@class="pill"]')[1]

	# Yellow card
	yc_path = './/span[contains(@class, "yellow-card")]'
	yc = data.find_elements_by_xpath(yc_path)
	yc = 1 if yc else 0

	# Red card
	rc_path = './/span[contains(@class, "red-card")]'
	rc = data.find_elements_by_xpath(rc_path)
	rc = 1 if rc else 0

	return yc, rc


def get_grade(player: webdriver) -> float:

	# Select alvin element
	data = player.find_elements_by_xpath('.//div[@class="pill"]')[1]

	grade_path = './/span[contains(@class, "player-grade")]'
	grade_elem = data.find_element_by_xpath(grade_path)
	grade = grade_elem.get_attribute('data-value')

	# When player did not play enough minutes value is 55 in webpage
	return float(grade.replace(',', '.')) if grade != '55' else 0.


def scrape_votes(brow: webdriver) -> webdriver:

	starting_day = last_day_played() + 1
	for day in range(starting_day, cfg.N_DAYS + 1):

		url = cfg.VOTES_URL + str(day)
		brow.get(url)
		time.sleep(3)

		all_tables = brow.find_elements_by_xpath(
				'.//table[@class="grades-table"]')
		if not all_tables:
			return brow

		for table in all_tables:
			team = table.find_element_by_xpath(
					'.//a[contains(@class, "team-name")]').text

			players = table.find_elements_by_xpath('.//tbody/tr')[:-1]
			for player in players:
				alvin = get_grade(player)
				if not alvin:
					continue

				nm = format_player_name(player_name=player.text)
				regular, going_in, going_out = regular_or_from_bench(player)
				amm, esp = get_yellow_red_cards(player)

				# Bonus and malus
				bn_ml = player.find_elements_by_xpath(
						'.//span[contains(@class, "player-bonus")]')
				bn_ml = [i.get_attribute('data-value') for i in bn_ml]
				bn_ml = [int(i) for i in bn_ml]
				gf, gs, au, rf, rs, rp, ass = bn_ml

				# Update db
				dbf.db_insert(
						table='votes',
						columns=['day', 'name', 'team', 'alvin',
						         'gf', 'gs', 'rp', 'rs', 'rf', 'au', 'amm',
						         'esp', 'ass', 'regular', 'going_in',
						         'going_out'],
						values=[day, nm, team, alvin,
						        gf, gs, rp, rs, rf, au, amm,
						        esp, ass, regular, going_in,
						        going_out])

	return brow


def scroll_to_element(brow: webdriver, element: webdriver,
                      position: str = '{block: "center"}') -> None:

	"""
	If the argument of 'scrollIntoView' is 'true' the command scrolls
	the webpage positioning the element at the top of the window, if it
	is 'false' the element will be positioned at the bottom.
	"""

	brow.execute_script(
			f'return arguments[0].scrollIntoView({position});',
			element)


def wait_visible(brow: webdriver, seconds: int, element_path: str) -> None:

	"""
	Forces the script to wait for the element to be visible before doing
	any other action.
	"""

	WebDriverWait(
			brow, seconds).until(ec.visibility_of_element_located(
					(By.XPATH, element_path)))


def no_more_days_to_scrape(brow: webdriver, day_to_scrape: int) -> bool:

	# Check if day in the webpage is the same as the day to scrape
	real_day_path = './/div[@class="filter-option-inner-inner"]'
	wait_visible(brow, cfg.WAIT, real_day_path)
	real_day = brow.find_element_by_xpath(real_day_path)
	real_day = int(real_day.text.split('°')[0])
	return True if day_to_scrape != real_day else False


def calculate_mv(player: str) -> (int, float):

	"""
	Calculate vote average for player.
	"""

	votes = dbf.db_select(table='votes',
	                      columns=['alvin'],
	                      where=f'name = "{player}"')
	matches = len(votes)
	return (matches, round(sum(votes)/matches, 2)) if matches else (0, 0.0)


def calculate_all_bonus(player: str) -> int:

	"""
	Calculate total bonus for player.
	"""

	plus1 = dbf.db_select(table='votes',
	                      columns=['ass'],
	                      where=f'name = "{player}"')
	plus1 = sum(plus1)

	plus3 = dbf.db_select(table='votes',
	                      columns=['gf', 'rp', 'rf'],
	                      where=f'name = "{player}"')
	plus3 = sum([sum(i) for i in plus3]) * 3

	return plus1 + plus3


def calculate_all_malus(player: str) -> float:

	"""
	Calculate total malus for player.
	"""

	minus05 = dbf.db_select(table='votes',
	                        columns=['amm'],
	                        where=f'name = "{player}"')
	minus05 = sum(minus05) * .5

	minus1 = dbf.db_select(table='votes',
	                       columns=['gs', 'esp'],
	                       where=f'name = "{player}"')
	minus1 = sum([sum(i) for i in minus1])

	minus2 = dbf.db_select(table='votes',
	                       columns=['au'],
	                       where=f'name = "{player}"')
	minus2 = sum(minus2) * 2

	minus3 = dbf.db_select(table='votes',
	                       columns=['rs'],
	                       where=f'name = "{player}"')
	minus3 = sum(minus3) * 3

	return minus05 + minus1 + minus2 + minus3


def calculate_regular_in_out(player: str) -> (int, int, int):

	"""
	Calculate matches from beginning, going in and going out for player.
	"""

	regular = dbf.db_select(table='votes',
	                        columns=['regular'],
	                        where=f'name = "{player}"')

	going_in = dbf.db_select(table='votes',
	                         columns=['going_in'],
	                         where=f'name = "{player}"')

	going_out = dbf.db_select(table='votes',
	                          columns=['going_out'],
	                          where=f'name = "{player}"')

	return sum(regular), sum(going_in), sum(going_out)


def update_stats() -> None:

	"""
	Update database used for market with stats.
	"""

	names_in_stats = dbf.db_select(table='stats',
	                               columns=['name'],
	                               where='')

	players = open_excel_file(cfg.QUOTAZIONI_FILENAME)

	for row in range(players.shape[0]):
		roles, name, team, price = players.iloc[row][
			['RM', 'Nome', 'Squadra', 'Qt.A M']
		]
		name = format_player_name(player_name=name)
		matches, mv = calculate_mv(name)
		bonus = calculate_all_bonus(name)
		malus = calculate_all_malus(name)
		mfv = round(mv + (bonus - malus)/matches, 2) if matches else 0
		regular, going_in, going_out = calculate_regular_in_out(name)

		if name in names_in_stats:
			dbf.db_update(table='stats',
			              columns=['name', 'team', 'roles', 'mv', 'mfv',
			                       'regular', 'going_in', 'going_out',
			                       'price'],
			              values=[name, team, roles, mv, mfv, regular,
			                      going_in, going_out, price],
			              where=f'name = "{name}"')
		else:
			dbf.db_insert(table='stats',
			              columns=['name', 'team', 'roles', 'status', 'mv',
			                       'mfv', 'regular', 'going_in', 'going_out',
			                       'price'],
			              values=[name, team, roles, 'FREE', mv, mfv, regular,
			                      going_in, going_out, price])

	os.remove(cfg.QUOTAZIONI_FILENAME)


if __name__ == '__main__':

	browser = manage_adblock()
	scrape_votes(browser)
	scrape_lineups_schemes_points(brow=browser)
	scrape_classifica(brow=browser)
	browser.quit()

	if os.path.isfile(cfg.QUOTAZIONI_FILENAME):
		update_stats()
