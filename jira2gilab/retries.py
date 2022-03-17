import time
from functools import wraps
import logging
mylog = logging.getLogger(__name__)


def on_except_retry(pause=0, retryes=2, except_class=Exception, reraise=True, default=None):
    """
    На возникновение ошибки, повторить вызов метода

    :param pause: пауза между попытками
    :param retryes: кол-во попыток
    :param except_class: класс исключения на который реагировать
    :param reraise: возбуждать исключение по окончанию попыток
    :param default: возращаемое значение в случае неудачи
    :return:
    """

    def decor(f):

        @wraps(f)
        def wrapped(*args, **kwargs):
            fail_count = 0
            while fail_count < retryes:
                if fail_count > 0:
                    time.sleep(pause)
                    mylog.warning("Повторный вызов: {}.{}; попытка:{}".format(f.__module__, f.__name__, fail_count))
                try:
                    r = f(*args, **kwargs)
                    # подсчет успешных вызовов для вычисления статистики
                    return r
                except except_class as e:
                    fail_count += 1

                    mylog.error("Ошибка вызова N{} {}.{}; {}".format(fail_count, f.__module__, f.__name__, repr(e)))
                    # вывод статистики о вызовах
                    
                    mylog.exception(e)
                    if fail_count >= retryes and reraise:
                        raise e
            return default
        return wrapped
    return decor