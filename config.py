import os

# Set paths
MAIN_DIR = '/Users/andrea/Desktop/Cartelle/Bots'
DB_LEAGUE = f'{MAIN_DIR}/FantaScandalo/fantascandalo_db.db'
DB_MARKET = f'{MAIN_DIR}/FantAstaBot/fanta_asta_db.db'

# update_database.py
CHROME_PATH = os.getcwd() + '/chromedriver'
WAIT = 10
FANTASCANDALO_URL = 'https://leghe.fantacalcio.it/fantascandalo/'
VOTES_URL = 'https://www.fantacalcio.it/voti-fantacalcio-serie-a/2022-23/'
QUOTAZIONI_FILENAME = ('/Users/andrea/Downloads/Quotazioni_' +
                       'Fantacalcio_Stagione_2022_23.xlsx')

# utils.py
ALL_LEAGUES = ('/Users/andrea/Desktop/Cartelle/FantaScandalo/'
               'All_Leagues_8teams.txt')

N_TEAMS = 8
N_DAYS = 35
