import pandas as pd
import numpy as np
from nltk.metrics.distance import jaccard_distance
from nltk.util import ngrams

import config_asta as cfa
import db_functions as dbf


def insert_players_first_time():

    players = pd.read_excel(io=cfa.QUOTAZIONI,
                            sheet_name="Tutti",
                            usecols=[1, 2, 3, 4],
                            engine='openpyxl')

    for x in range(1, len(players)):
        roles, name, team, price = players.iloc[x].values
        dbf.db_insert(table='players',
                      columns=['name', 'team', 'roles', 'price', 'status'],
                      values=[name.strip().title(), team.strip(),
                              roles.strip(), int(price), 'FREE'],
                      database=cfa.DB_NAME)


def jaccard_result(name_to_fix: str, all_options: list, ngrams_lenght: int):

    name_to_correct = name_to_fix.lower().replace(' ', '')
    n_in = set(ngrams(name_to_correct, ngrams_lenght))

    out_opts = [pl.lower().replace(' ', '') for pl in all_options]
    n_outs = [set(ngrams(pl, ngrams_lenght)) for pl in out_opts]

    distances = [jaccard_distance(n_in, n_out) for n_out in n_outs]

    if len(set(distances)) == 1 and distances[0] == 1:
        return jaccard_result(name_to_correct, all_options, ngrams_lenght-1)
    else:
        return np.array(all_options)[np.argsort(distances)][:3]


def start_asta():
    print('Type PLAYER_NAME, FANTATEAM, PRICE:')

    try:
        nm, tm, pr = input().split(',')
    except ValueError:
        print('WRONG FORMAT')
        return start_asta()

    all_tm = dbf.db_select(table='teams',
                           columns=['team_name'],
                           where='',
                           database=cfa.DB_NAME)
    a = jaccard_result(name_to_fix=tm, all_options=all_tm, ngrams_lenght=3)
    print()


start_asta()
