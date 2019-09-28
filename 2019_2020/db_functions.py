import sqlite3

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


def start_db():

    db = sqlite3.connect(database)
    c = db.cursor()
    c.execute("PRAGMA foreign_keys = ON")

    return db, c
