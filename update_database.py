import os
import time
import db_functions as dbf
import pandas as pd
from collections import defaultdict
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.by import By
from selenium import webdriver

CHROME_PATH = os.getcwd() + '/chromedriver'
WAIT = 10
YEAR = '2019-20'
BASE_URL = 'https://leghe.fantacalcio.it/fantascandalo/'


def add_6_politico_if_needed(day):

	"""
	Assign 6 to each player of the matches which have not been played.

	:param day: int

	"""

	teams_in_day = set(dbf.db_select(
			table='votes',
			columns=['team'],
			where=f'day = {day}'))
	if len(teams_in_day) == 20:
		return

	all_teams = set(dbf.db_select(table='votes', columns=['team']))
	missing = all_teams - teams_in_day

	votes_of_day = dbf.db_select(
			table='votes',
			columns=['day', 'name', 'team', 'fg', 'alvin', 'italia', 'gf',
			         'gs', 'rp', 'rs', 'rf', 'au', 'amm', 'esp', 'ass',
			         'regular', 'going_in', 'going_out'],
			where=f'day = {day}')

	for team in missing:
		shortlist = dbf.db_select(
				table='all_players_serie_a',
				columns=['day_{}'.format(day)],
				where=f'team = "{team}"')[0]
		shortlist = shortlist.split(', ')

		for nm in shortlist:
			data = (day, nm, team, 6, 6, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
			votes_of_day.append(data)

	votes_of_day.sort(key=lambda x: x[2])
	dbf.db_delete(table='votes', where=f'day = {day}')

	for row in votes_of_day:
		dbf.db_insert(
				table='votes',
				columns=['day', 'name', 'team', 'fg', 'alvin', 'italia',
				         'gf', 'gs', 'rp', 'rs', 'rf', 'au', 'amm',
				         'esp', 'ass', 'regular', 'going_in', 'going_out'],
				values=[value for value in row])


def close_popup(brow):

	"""
	Close popup.

	:param brow: selenium browser instance

	"""

	accetto = './/button[@class="qc-cmp-button"]'

	try:
		wait_clickable(brow, WAIT, accetto)
		brow.find_element_by_xpath(accetto).click()
	except TimeoutException:
		pass


def last_day_played():

	"""
	Return last day which has been played. Last day played is defined as the
	last day in the db where absolute points are saved.

	:return: int

	"""

	list_of_abs_points = dbf.db_select(table='absolute_points',
	                                   columns=['*'])[0][1:]

	try:
		return list_of_abs_points.index(None)
	except ValueError:
		# Updating after the last day of the league will give a ValueError
		return len(list_of_abs_points)


def open_excel_file(filename):

	"""
	Try opening the file until found.

	:param filename: str, path of the file to open

	"""

	while True:

		try:
			players = pd.read_excel(filename, sheet_name='Tutti',
			                        header=1)
			return players
		except FileNotFoundError:
			continue


def manage_adblock():

	"""
	Start the browser with adblock.

	:return: selenium browser instance

	"""

	# Use AdBlock
	chop = webdriver.ChromeOptions()
	chop.add_extension('AdBlock_v3.34.0.crx')
	chop.add_argument("--disable-infobars")
	brow = webdriver.Chrome(CHROME_PATH, chrome_options=chop)
	time.sleep(10)

	handles = brow.window_handles
	brow.switch_to.window(handles[1])
	brow.close()
	brow.switch_to.window(handles[0])

	return brow


def scrape_lineups_schemes_points():

	"""
	Scrape lineups, schemes and absolute points and update database.

	"""

	brow = manage_adblock()

	# To know if it is the first iteration. If yes, close the popup
	first2scrape = True

	# To know if absolute points need to be scraped. It will be False when
	# scraping lineups of the current day, still incomplete
	scrape_points = True

	starting_day = last_day_played() + 1
	for day in range(starting_day, 36):

		brow.get(f'{BASE_URL}formazioni/{day}')

		if first2scrape:
			close_popup(brow)
			first2scrape = False
		time.sleep(5)

		# The actual day of the league. We need it to know when stop scraping
		real_day = './/div[@class="filter-option-inner-inner"]'
		wait_visible(brow, WAIT, real_day)
		real_day = int(brow.find_element_by_xpath(real_day).text.split('°')[0])
		if day != real_day:
			break

		# If some lineup is missing, stop
		missing_lineups = len(brow.find_elements_by_xpath(
				'.//div[contains(@class, "hidden-formation")]'))
		if missing_lineups:
			break

		# Find all matches
		matches = brow.find_elements_by_xpath(
				'.//div[contains(@class, "match-details card calculated")]')
		if not matches:
			# If day it is not concluded it has a different attribute
			matches = brow.find_elements_by_xpath(
					'.//div[contains(@class, "match-details")]')
			scrape_points = False

		# Iterate the matches and update database
		for match in matches:
			scroll_to_element(brow, match)
			teams = match.find_elements_by_xpath(
					'.//h4[@class="media-heading ellipsis"]')
			schemes = match.find_elements_by_xpath('.//h5')
			first11 = match.find_elements_by_xpath(
					'.//table[@id="formationTable"]')
			reserves = match.find_elements_by_xpath(
					'.//table[@id="releaseTable"]')
			points = match.find_elements_by_xpath(
					'.//div[@class="team-main-info"]')
			time.sleep(1)

			for team, scheme, table1, table2, score in zip(
					teams, schemes, first11, reserves, points):

				team_name = ''
				while not team_name:
					scroll_to_element(brow, team)
					team_name = team.text

				captain = None
				vice = None
				complete_lineup = []

				players = table1.find_elements_by_xpath(
						'.//tr[contains(@class, "player-list-item")]')
				players += table2.find_elements_by_xpath(
						'.//tr[contains(@class, "player-list-item")]')[:-1]
				for player in players:
					name = ''
					while not name:
						scroll_to_element(brow, player)
						name = player.find_element_by_xpath(
							'.//span[@class="player-name ellipsis"]').text
						name = name.replace('.', '')
					complete_lineup.append(name)

					try:
						player.find_element_by_xpath(
								'.//li[@data-original-title="Capitano"]')
						captain = name
					except NoSuchElementException:
						pass

					try:
						player.find_element_by_xpath(
								'.//li[@data-original-title="Vice capitano"]')
						vice = name
					except NoSuchElementException:
						pass

				captains = f'{captain}, {vice}'
				complete_lineup = ', '.join(complete_lineup)

				dbf.db_update(
						table='captains',
						columns=[f'day_{day}'],
						values=[captains.upper()],
						where=f'team_name="{team_name}"')

				dbf.db_update(
						table='lineups',
						columns=[f'day_{day}'],
						values=[complete_lineup.upper()],
						where=f'team_name="{team_name}"')

				scroll_to_element(brow, scheme)
				dbf.db_update(
						table='schemes',
						columns=[f'day_{day}'],
						values=[scheme.text.split('\n')[0]],
						where=f'team_name="{team_name}"')

				if scrape_points:
					scroll_to_element(brow, score)
					score = float(score.text.split('\n')[0])
					dbf.db_update(
							table='absolute_points',
							columns=[f'day_{day}'],
							values=[score],
							where=f'team_name="{team_name}"')

	return brow


def scrape_allplayers_fantateam(brow):

	"""
	Scrape the complete set of players per each fantateam, day by day.

	:param brow: selenium browser instance

	:return brow: selenium browser instance

	"""

	# Used later to fill the right cell in the 'all_players' table
	days_played = last_day_played()

	# Go the webpage
	brow.get(f'{BASE_URL}rose')

	# Wait for this element to be visible
	check = './/h4[@class="has-select clearfix public-heading"]'
	wait_visible(brow, WAIT, check)

	# Find all the tables containing the shortlists
	shortlists = ('.//li[contains(@class,'
	              '"list-rosters-item raised-2 current-competition-team")]')
	shortlists = brow.find_elements_by_xpath(shortlists)
	for shortlist in shortlists:

		# Name of the fantateam
		team_name = ''
		while not team_name:
			team = shortlist.find_element_by_xpath('.//h4')
			team_name = team.get_attribute('innerText').strip()

		# Names containers
		players = []
		names = shortlist.find_elements_by_xpath('.//td[@data-key="name"]')
		for player in names:
			name = player.get_attribute('innerText').upper().strip()
			name = name.replace('.', '')
			players.append(name)

		# Update "all_players" table
		dbf.db_update(
				table='all_players',
				columns=[f'day_{days_played}'],
				values=[', '.join(players)],
				where=f'team_name = "{team_name}"')

		# Update "stats" table
		update_players_status_in_stats(team_name, players)

	return brow


def update_players_status_in_stats(team_name, list_of_players):

	"""
	:param team_name: str
	:param list_of_players: list
	"""

	# First set all players of team as FREE
	dbf.db_update(
			table='stats',
			columns=['status'],
			values=['FREE'],
			where=f'status = "{team_name}"')

	# Then update the status
	for player in list_of_players:
		dbf.db_update(
				table='stats',
				columns=['status'],
				values=[team_name],
				where=f'name = "{player}"')


def scrape_classifica(brow):

	"""
	Scrape real data from website in order to check later how the algorithm is
	working.

	:param brow: selenium browser instance

	"""

	brow.get(f'{BASE_URL}classifica')
	time.sleep(3)

	dbf.empty_table(table='classifica')

	positions = brow.find_elements_by_xpath(
			'.//table/tbody/tr[contains(@data-logo, ".png")]')

	columns = ['team', 'G', 'V', 'N', 'P', 'Gf', 'Gs', 'Dr', 'Pt', 'Tot']
	for pos in positions:
		team_data = []
		scroll_to_element(brow, pos)
		fields = pos.find_elements_by_xpath(
			'.//td')[2:-2]

		for field in fields:
			team_data.append(field.text)

		dbf.db_insert(table='classifica',
		              columns=columns,
		              values=team_data)

	brow.close()


def scrape_roles_and_players_serie_a(brow):

	"""
	Scrape all players from each real team in Serie A and their roles.
	Players are used when 6 politico is needed.

	:param brow: selenium browser instance

	:return: selenium browser instance

	"""

	# Players which are already in the db with their roles
	already_in_db = dbf.db_select(table='roles', columns=['name'])

	# Download excel file with the data
	# url = 'https://www.fantacalcio.it/quotazioni-fantacalcio/mantra'
	# brow.get(url)
	# close_popup(brow)
	# time.sleep(3)
	# button = './/button[@id="toexcel"]'
	# wait_visible(brow, WAIT, button)
	# brow.find_element_by_xpath(button).click()
	# time.sleep(2)

	# Load file and remove it from local
	filename = ('/Users/andrea/Downloads/Quotazioni_' +
	            'Fantacalcio_Ruoli_Mantra.xlsx')

	players = open_excel_file(filename)

	# Create dict where keys are the teams of Serie A and values are lists
	# containing their players
	shortlists = defaultdict(list)
	for row in range(len(players)):
		rl, nm, tm = players.loc[row, ['R', 'Nome', 'Squadra']].values
		nm = nm.replace('.', '')
		shortlists[tm.upper()].append(nm)

		# Update roles in the db
		if nm not in already_in_db:
			dbf.db_insert(
					table='roles',
					columns=['name', 'role'],
					values=[nm, rl])

	# Update the db
	teams_in_db = dbf.db_select(
			table='all_players_serie_a',
			columns=['team'])

	days_played = last_day_played()
	for team, shortlist in shortlists.items():
		shortlist = ', '.join(shortlist)
		if team not in teams_in_db:
			dbf.db_insert(
					table='all_players_serie_a',
					columns=['team', 'day_1'],
					values=[team.upper(), shortlist])
		else:
			dbf.db_update(
					table='all_players_serie_a',
					columns=[f'day_{days_played}'],
					values=[shortlist],
					where=f'team = "{team}"')

	return brow


def regular_or_from_bench(player):

	"""
	Set info about playing and substitutions for each player.

	:param player: selenium element

	:return: tuple, (int, int, int)

	"""

	in_out = player.find_elements_by_xpath('.//td/em')
	attrs = [i.get_attribute('title') for i in in_out]

	regular = 0
	going_in = 0
	going_out = 0
	if 'Entrato' not in attrs and 'Uscito' not in attrs:
		regular += 1
	elif 'Entrato' in attrs and 'Uscito' not in attrs:
		going_in += 1
	elif 'Entrato' not in attrs and 'Uscito' in attrs:
		regular += 1
		going_out += 1
	elif 'Entrato' in attrs and 'Uscito' in attrs:
		going_in += 1
		going_out += 1

	return regular, going_in, going_out


def scrape_votes(brow):

	"""
	Download the excel file with the votes day by day and update the db.
	:param brow: selenium browser instance

	"""

	days_played = last_day_played()
	main_url = f'https://www.fantacalcio.it/voti-fantacalcio-serie-a/{YEAR}/'

	for day in range(1, days_played + 1):

		if wrong_day_to_scrape(day):
			continue

		url = main_url + str(day)
		brow.get(url)

		all_tables = brow.find_elements_by_xpath('.//table[@role="grid"]')
		for table in all_tables:
			team = table.find_element_by_xpath('.//span[@class="txtbig"]')
			scroll_to_element(brow, team)
			team = team.get_attribute('innerText')

			players = table.find_elements_by_xpath('.//tbody/tr')[:-1]
			for player in players:
				regular, going_in, going_out = regular_or_from_bench(player)
				data = player.find_elements_by_xpath('.//td')
				del data[1]

				nm = data[0].find_element_by_xpath(
						'.//a').get_attribute('innerText')
				nm = nm.replace('.', '')
				alvin = data[3].find_element_by_xpath(
						'.//span').get_attribute('innerText')
				color = data[3].find_element_by_xpath(
						'.//span').get_attribute('class')
				if 'grey' in color:
					alvin = 'sv'
					going_in = 0
				else:
					alvin = float(alvin.replace(',', '.'))
				try:
					data[3].find_element_by_xpath(
							'.//span[contains(@class, "trn-r trn-ry absort")]')
					amm = 1
				except NoSuchElementException:
					amm = 0
				try:
					data[3].find_element_by_xpath(
							'.//span[contains(@class, "trn-r trn-rr absort")]')
					esp = 1
				except NoSuchElementException:
					esp = 0

				try:
					gf = data[7].find_element_by_xpath(
							'.//span').get_attribute('innerText')
				except NoSuchElementException:
					gf = 0
				try:
					rf = data[8].find_element_by_xpath(
							'.//span').get_attribute('innerText')
				except NoSuchElementException:
					rf = 0
				try:
					gs = data[9].find_element_by_xpath(
							'.//span').get_attribute('innerText')
				except NoSuchElementException:
					gs = 0
				try:
					rp = data[10].find_element_by_xpath(
							'.//span').get_attribute('innerText')
				except NoSuchElementException:
					rp = 0
				try:
					rs = data[11].find_element_by_xpath(
							'.//span').get_attribute('innerText')
				except NoSuchElementException:
					rs = 0
				try:
					au = data[12].find_element_by_xpath(
							'.//span').get_attribute('innerText')
				except NoSuchElementException:
					au = 0
				try:
					ass = data[13].find_element_by_xpath(
							'.//span').get_attribute('innerText')
					if len(ass) == 1:
						ass = int(ass)
					else:
						ass = int(ass[0])
				except NoSuchElementException:
					ass = 0

				# Update db
				dbf.db_insert(
						table='votes',
						columns=['day', 'name', 'team', 'alvin',
						         'gf', 'gs', 'rp', 'rs', 'rf', 'au', 'amm',
						         'esp', 'ass', 'regular', 'going_in',
						         'going_out'],
						values=[day, nm.strip(), team, alvin,
						        gf, gs, rp, rs, rf, au, amm,
						        esp, ass, regular, going_in,
						        going_out])

		add_6_politico_if_needed(day)
	return brow


def scroll_to_element(brow, element, position='{block: "center"}'):

	"""
	If the argument of 'scrollIntoView' is 'true' the command scrolls
	the webpage positioning the element at the top of the window, if it
	is 'false' the element will be positioned at the bottom.
	"""

	brow.execute_script(
			f'return arguments[0].scrollIntoView({position});',
			element)


def wait_clickable(brow, seconds, element):

	"""
	Forces the script to wait for the element to be clickable before doing
	any other action.

	:param brow:
	:param seconds: int, maximum wait before returning a TimeoutException
	:param element: str, xpath of the element

	:return: nothing

	"""

	WebDriverWait(
			brow, seconds).until(ec.element_to_be_clickable(
					(By.XPATH, element)))


def wait_visible(brow, seconds, element):

	"""
	Forces the script to wait for the element to be visible before doing
	any other action.

	:param brow:
	:param seconds: int, maximum wait before returning a TimeoutException
	:param element: str, xpath of the element

	:return: nothing

	"""

	WebDriverWait(
			brow, seconds).until(ec.visibility_of_element_located(
					(By.XPATH, element)))


def wrong_day_to_scrape(day):

	"""
	Check if we need to scrape votes relative to 'day'.

	:param day: int

	:return: bool

	"""

	teams_in_db = set(dbf.db_select(
			table='votes',
			columns=['team'],
			where=f'day = {day}'))

	if len(teams_in_db) == 20:
		return True
	else:
		return False


def calculate_mv(player):

	"""
	Calculate vote average for player.

	:param player: str

	:return: tuple
	"""

	votes = dbf.db_select(table='votes',
	                      columns=['alvin'],
	                      where=f'name = "{player}" AND alvin != "sv"')
	matches = len(votes)

	return matches, round(sum(votes)/matches, 2) if matches else 0


def calculate_all_bonus(player):

	"""
	Calculate total bonus for player.

	:param player: str

	:return: int
	"""
	plus1 = dbf.db_select(table='votes',
	                      columns=['ass'],
	                      where=f'name = "{player}"')
	plus1 = sum(plus1)

	plus3 = dbf.db_select(table='votes',
	                      columns=['gf', 'rp', 'rf'],
	                      where=f'name = "{player}"')
	plus3 = sum([sum(i) for i in plus3])*3

	return plus1 + plus3


def calculate_all_malus(player):

	"""
	Calculate total malus for player.

	:param player: str

	:return: float
	"""
	minus05 = dbf.db_select(table='votes',
	                        columns=['amm'],
	                        where=f'name = "{player}"')
	minus05 = sum(minus05)*.5

	minus1 = dbf.db_select(table='votes',
	                       columns=['gs', 'esp'],
	                       where=f'name = "{player}"')
	minus1 = sum([sum(i) for i in minus1])

	minus2 = dbf.db_select(table='votes',
	                       columns=['au'],
	                       where=f'name = "{player}"')
	minus2 = sum(minus2)*2

	minus3 = dbf.db_select(table='votes',
	                       columns=['rs'],
	                       where=f'name = "{player}"')
	minus3 = sum(minus3) * 3

	return minus05 + minus1 + minus2 + minus3


def calculate_regular_in_out(player):

	"""
	Calculate matches from beginning, going in and going out for player.

	:param player: str

	:return: tuple
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


def update_stats():

	"""
	Update database used for market with stats.
	"""

	names_in_stats = dbf.db_select(table='stats',
	                               columns=['name'],
	                               database=dbf.dbase1)

	filename = ('/Users/andrea/Downloads/Quotazioni_' +
	            'Fantacalcio_Ruoli_Mantra.xlsx')
	players = open_excel_file(filename)

	for row in range(players.shape[0]):
		roles, name, team, price = players.iloc[row][['R', 'Nome',
		                                              'Squadra', 'Qt. A']]
		name = name.replace('.', '')
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
			              where=f'name = "{name}"',
			              database=dbf.dbase1)
		else:
			print('New name for stats: ', name)
			dbf.db_insert(table='stats',
			              columns=['name', 'team', 'roles', 'status', 'mv',
			                       'mfv', 'regular', 'going_in', 'going_out',
			                       'price'],
			              values=[name, team, roles, 'FREE', mv, mfv, regular,
			                      going_in, going_out, price],
			              database=dbf.dbase1)

	os.remove(filename)


def update_market_db():

	"""
	Update the db used for market.
	"""

	# Update table "classifica"
	cols = ['team', 'G', 'V', 'N', 'P', 'Gf', 'Gs', 'Dr', 'Pt', 'Tot']
	dbf.empty_table(table='classifica', database=dbf.dbase2)
	data = dbf.db_select(table='classifica', columns=cols)
	for el in data:
		dbf.db_insert(
				table='classifica',
				columns=cols,
				values=el,
				database=dbf.dbase2)

	# Update table "players"
	cols = ['name', 'team', 'roles', 'price', 'status']
	dbf.empty_table(table='players', database=dbf.dbase2)
	data = dbf.db_select(
			table='stats',
			columns=cols)
	for el in data:
		dbf.db_insert(
				table='players',
				columns=[f'player_{i}' for i in cols],
				values=el,
				database=dbf.dbase2)


if __name__ == '__main__':

	browser = scrape_lineups_schemes_points()
	browser = scrape_allplayers_fantateam(browser)
	scrape_roles_and_players_serie_a(browser)
	scrape_votes(browser)
	scrape_classifica(browser)

	update_stats()
	update_market_db()