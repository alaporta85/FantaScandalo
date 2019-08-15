import sqlite3

database = 'fantascandalo_db.db'


def db_insert(table, columns, values):

    """
    Insert a new row in the table.

    :param table: str, name of the table

    :param columns: list, each element of the list is a column of the table.

    :param values: list, values of the corresponding columns

    """

    db, c = start_db()

    placeholders = ['"{}"' if type(v) == str else '{}' for v in values]
    vals = [el[0].format(el[1]) for el in zip(placeholders, values)]

    c.execute('''INSERT INTO {} ({}) VALUES ({})'''.
              format(table, ','.join(columns), ','.join(vals)))

    db.commit()
    db.close()


def db_select(table, columns, where=None):

    """
    Return content from a specific table of the database.

    :param table: str, name of the table

    :param columns: list, each element of the list is a column of the table.

    :param where: str, condition. Ex: 'pred_label == WINNING'


    :return: list of tuples or list of elements

    """

    db, c = start_db()

    if where:
        query = """SELECT {} FROM {} WHERE {}""".format(', '.join(columns),
                                                        table, where)
    else:
        query = '''SELECT {} FROM {}'''.format(', '.join(columns), table)

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

    placeholders = ['"{}"' if type(v) == str else '{}' for v in values]
    vals = [el[0].format(el[1]) for el in zip(placeholders, values)]
    vals = ["{}={}".format(el[0], el[1]) for el in zip(columns, vals)]

    c.execute("UPDATE {} SET {} WHERE {}".format(table, ','.join(vals), where))

    db.commit()
    db.close()


def start_db():

    db = sqlite3.connect(database)
    c = db.cursor()
    c.execute("PRAGMA foreign_keys = ON")

    return db, c
