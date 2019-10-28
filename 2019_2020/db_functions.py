import sqlite3
import numpy as np
from nltk.metrics.distance import jaccard_distance
from nltk.util import ngrams

database = 'fantascandalo_db.db'


def empty_table(table):

    """
    Delete everything from table.

    :param table: str

    """

    db, c = start_db()

    query = f'DELETE FROM {table}'

    c.execute(query)
    db.commit()
    db.close()


def db_delete(table, where):

    """
    Remove entry from database.

    :param table: str
    :param where: str

    """

    db, c = start_db()

    query = f'DELETE FROM {table} WHERE {where}'

    c.execute(query)
    db.commit()
    db.close()


def db_insert(table, columns, values):

    """
    Insert a new row in the table.

    :param table: str, name of the table
    :param columns: list, each element of the list is a column of the table.
    :param values: list, values of the corresponding columns

    """

    db, c = start_db()

    cols = ', '.join(columns)
    vals = ', '.join([f'"{v}"' for v in values])
    query = f'INSERT INTO {table} ({cols}) VALUES ({vals})'

    c.execute(query)
    db.commit()
    db.close()


def db_select(table, columns, where=None):

    """
    Return content from a specific table of the database.

    :param table: str, name of the table
    :param columns: list, each element of the list is a column of the table.
    :param where: str, condition

    :return: list of tuples or list of elements

    """

    db, c = start_db()

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


def db_update(table, columns, values, where):

    """
    Update values in the table.

    :param table: str, name of the table
    :param columns: list, each element of the list is a column of the table.
    :param values: list, values of the corresponding columns
    :param where: str, condition

    """

    db, c = start_db()

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


def start_db():

    db = sqlite3.connect(database)
    c = db.cursor()
    c.execute("PRAGMA foreign_keys = ON")

    return db, c
