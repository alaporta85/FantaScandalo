import sqlite3
import numpy as np
from nltk.metrics.distance import jaccard_distance
from nltk.util import ngrams
import config as cfg


def empty_table(table: str, database: str = cfg.DB_LEAGUE):

    db, c = start_db(database)

    query = f'DELETE FROM {table}'

    c.execute(query)
    db.commit()
    db.close()


def db_delete(table: str, where: str, database: str = cfg.DB_LEAGUE):

    db, c = start_db(database)

    query = f'DELETE FROM {table} WHERE {where}'

    c.execute(query)
    db.commit()
    db.close()


def db_insert(table: str, columns: list, values: list,
              database: str = cfg.DB_LEAGUE):

    db, c = start_db(database)

    cols = ', '.join(columns)
    vals = ', '.join([f'"{v}"' for v in values])
    query = f'INSERT INTO {table} ({cols}) VALUES ({vals})'

    c.execute(query)
    db.commit()
    db.close()


def db_select(table: str, columns: list, where: str,
              database: str = cfg.DB_LEAGUE):

    db, c = start_db(database)

    cols = ', '.join(columns)
    if where:
        query = f'SELECT {cols} FROM {table} WHERE {where}'
    else:
        query = f'SELECT {cols} FROM {table}'

    content = list(c.execute(query))
    db.close()

    if len(columns) == 1 and columns[0] != '*':
        content = [el[0] for el in content]

    return content


def db_update(table: str, columns: list, values: list, where: str,
              database: str = cfg.DB_LEAGUE):

    db, c = start_db(database)

    vals = ', '.join([f'{c}="{v}"' for c, v in zip(columns, values)])
    query = f'UPDATE {table} SET {vals} WHERE {where}'

    c.execute(query)
    db.commit()
    db.close()


def jaccard_result(in_opt: str, all_opt: list, ngrm: int) -> str:

    in_opt = in_opt.lower().replace(' ', '')
    n_in = set(ngrams(in_opt, ngrm))

    out_opts = [pl.lower().replace(' ', '') for pl in all_opt]
    n_outs = [set(ngrams(pl, ngrm)) for pl in out_opts]

    distances = [jaccard_distance(n_in, n_out) for n_out in n_outs]

    if len(set(distances)) == 1:
        return jaccard_result(in_opt, all_opt, ngrm-1) if ngrm > 2 else ''
    else:
        idx = int(np.argmin(distances))
        return all_opt[idx]


def start_db(database: str) -> tuple:

    db = sqlite3.connect(database)
    c = db.cursor()
    c.execute("PRAGMA foreign_keys = ON")

    return db, c
