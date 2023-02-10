import logging
import logging.config
import yaml


def set_logging():

    """
    Logging configuration with a YAML format configuration file.
    flogger writes on logs/bet_bot.log file
    and RotatingFileHandler allows to rollover file
    at a predetermined size (maxBytes)

    """

    logging.config.dictConfig(yaml.load(open('logging.config'), yaml.Loader))
    flogger = get_flogger()

    return flogger


def get_flogger():

    """
    Returns a flogger instance

    """

    flogger = logging.getLogger('flogger')

    return flogger
