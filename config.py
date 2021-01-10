import os

dbase1 = 'fantascandalo_db.db'
dbase2 = '/Users/andrea/Desktop/Cartelle/Bots/FantAstaBot/fanta_asta_db.db'

# update_database.py
CHROME_PATH = os.getcwd() + '/chromedriver'
WAIT = 10
YEAR = '2020-21'
BASE_URL = 'https://leghe.fantacalcio.it/fantascandalo/'
VOTES_URL = f'https://www.fantacalcio.it/voti-fantacalcio-serie-a/{YEAR}/'
QUOTAZIONI_FILENAME = ('/Users/andrea/Downloads/Quotazioni_' +
                       'Fantacalcio_Ruoli_Mantra.xlsx')

# extra_functions.py
ALL_LEAGUES = ('/Users/andrea/Desktop/Cartelle/FantaScandalo/'
               'All_Leagues_8teams.txt')
