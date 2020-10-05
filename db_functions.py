import sqlite3
import numpy as np
from nltk.metrics.distance import jaccard_distance
from nltk.util import ngrams
import config as cfg


def empty_table(table, database=cfg.dbase1):

    """
    Delete everything from table.

    :param table: str
    :param database: str

    """

    db, c = start_db(database)

    query = f'DELETE FROM {table}'

    c.execute(query)
    db.commit()
    db.close()


def db_delete(table, where, database=cfg.dbase1):

    """
    Remove entry from database.

    :param table: str
    :param where: str
    :param database: str

    """

    db, c = start_db(database)

    query = f'DELETE FROM {table} WHERE {where}'

    c.execute(query)
    db.commit()
    db.close()


def db_insert(table, columns, values, database=cfg.dbase1):

    """
    Insert a new row in the table.

    :param table: str, name of the table
    :param columns: list, each element of the list is a column of the table.
    :param values: list, values of the corresponding columns
    :param database: str

    """

    db, c = start_db(database)

    cols = ', '.join(columns)
    vals = ', '.join([f'"{v}"' for v in values])
    query = f'INSERT INTO {table} ({cols}) VALUES ({vals})'

    c.execute(query)
    db.commit()
    db.close()


def db_select(table, columns, where=None, database=cfg.dbase1):

    """
    Return content from a specific table of the database.

    :param table: str, name of the table
    :param columns: list, each element of the list is a column of the table.
    :param where: str, condition
    :param database: str

    :return: list of tuples or list of elements

    """

    db, c = start_db(database)

    cols = ', '.join(columns)
    if where:
        query = f'SELECT {cols} FROM {table} WHERE {where}'
    else:
        query = f'SELECT {cols} FROM {table}'

    content = list(c.execute(query))
    db.close()

    if len(columns) == 1 and columns[0] != '*':
        content = [el[0] for el in content if el[0]]

    return content


def db_update(table, columns, values, where, database=cfg.dbase1):

    """
    Update values in the table.

    :param table: str, name of the table
    :param columns: list, each element of the list is a column of the table.
    :param values: list, values of the corresponding columns
    :param where: str, condition
    :param database: str

    """

    db, c = start_db(database)

    vals = ', '.join([f'{c}="{v}"' for c, v in zip(columns, values)])
    query = f'UPDATE {table} SET {vals} WHERE {where}'

    c.execute(query)
    db.commit()
    db.close()


def jaccard_result(in_opt, all_opt, ngrm):

    """
    Fix user input.

    :param in_opt: str
    :param all_opt: list
    :param ngrm: int, ngrams length

    :return jac_res: str

    """

    in_opt = in_opt.lower().replace(' ', '')
    n_in = set(ngrams(in_opt, ngrm))

    out_opts = [pl.lower().replace(' ', '') for pl in all_opt]
    n_outs = [set(ngrams(pl, ngrm)) for pl in out_opts]

    distances = [jaccard_distance(n_in, n_out) for n_out in n_outs]

    if len(set(distances)) == 1:
        return jaccard_result(in_opt, all_opt, ngrm-1) if ngrm > 2 else False
    else:
        return all_opt[np.argmin(distances)]


def start_db(database):

    db = sqlite3.connect(database)
    c = db.cursor()
    c.execute("PRAGMA foreign_keys = ON")

    return db, c
