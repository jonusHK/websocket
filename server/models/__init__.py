from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base
import inspect
import pkgutil
import importlib
import sys

DBSession = scoped_session(sessionmaker())
Base = declarative_base()


def initialize_sql(engine):
    DBSession.configure(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)


def import_models():
    thismodule = sys.modules[__name__]

    for loader, module_name, is_pkg in pkgutil.iter_modules(
            thismodule.__path__, thismodule.__name__ + '.'):
        module = importlib.import_module(module_name, loader.path)
        for name, _object in inspect.getmembers(module, inspect.isclass):
            globals()[name] = _object

import_models()
