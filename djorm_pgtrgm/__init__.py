# -*- coding: utf-8 -*-
"""Django ORM extension for PostgreSQL trigram indexing (`__similar` string search)"""


try:
    from django.db.models import Manager
    from django.db.models.query import QuerySet
    from django.db import backend
    from django.db import connection
    from django.db.models.fields import Field, subclassing
    from django.db.models.sql.constants import QUERY_TERMS
    from django.contrib.gis.db.models.sql.query import ALL_TERMS

    db_backends_allowed = ('postgresql', 'postgis')
    backend_allowed = reduce(
        lambda x, y: x in backend.__name__ or y, db_backends_allowed)

except:
    backend_allowed = None
    Manager = ImportError("Settings cannot be imported, because environment variable DJANGO_SETTINGS_MODULE is undefined.")
    QuerySet = Manager

__version__ = "0.1.1"
__authors__ = [
    u'José Antonio Leiva <jleivaizq@gmail.com>',
    u'Pablo Martín <goinnn@gmail.com>',
    'Hobson <hobson@totalgood.com>',
    ]
__github_url__ = "https://github.com/jleivaizq/djorm-ext-pgtrgm"   # % (__name__)



def get_prep_lookup(self, lookup_type, value):
    try:
        return self.get_prep_lookup_origin(lookup_type, value)
    except TypeError as e:
        if lookup_type in NEW_LOOKUP_TYPE:
            return value
        raise e


def get_db_prep_lookup(self, lookup_type, value, *args, **kwargs):
    try:
        value_returned = self.get_db_prep_lookup_origin(lookup_type, value,
                                                        *args, **kwargs)
    except TypeError as e:  # Django 1.1
        if lookup_type in NEW_LOOKUP_TYPE:
            return [value]
        raise e
    if value_returned is None and lookup_type in NEW_LOOKUP_TYPE:  # Dj > 1.1
        return [value]
    return value_returned


def monkey_get_db_prep_lookup(cls):
    cls.get_db_prep_lookup_origin = cls.get_db_prep_lookup
    cls.get_db_prep_lookup = get_db_prep_lookup
    if hasattr(subclassing, 'call_with_connection_and_prepared'):  # Dj > 1.1
        setattr(cls, 'get_db_prep_lookup',
                subclassing.call_with_connection_and_prepared(cls.get_db_prep_lookup))
        for new_cls in cls.__subclasses__():
            monkey_get_db_prep_lookup(new_cls)


if backend_allowed:

    if isinstance(QUERY_TERMS, set):
        QUERY_TERMS.add('similar')
    else:
        QUERY_TERMS['similar'] = None

    if backend_allowed == 'postgis':
        if isinstance(ALL_TERMS, set):
            ALL_TERMS.add('similar')
        else:
            ALL_TERMS['similar'] = None

    connection.operators['similar'] = "%%%% %s"

    NEW_LOOKUP_TYPE = ('similar', )

    monkey_get_db_prep_lookup(Field)
    if hasattr(Field, 'get_prep_lookup'):
        Field.get_prep_lookup_origin = Field.get_prep_lookup
        Field.get_prep_lookup = get_prep_lookup


class SimilarQuerySet(QuerySet):
    # Append the similarity score because a subsequent values or values_list might expect it due to the order_by
    def filter(self, **kwargs):
        qs = super(SimilarQuerySet, self).filter(**kwargs)
        for lookup, query in kwargs.items():
            if lookup.endswith('__similar'):
                field = lookup[:-9]
                select = {'%s_similarity' % field: "similarity(%s, '%s')" % (field, query)}
                qs = qs.extra(select=select)
        return qs

    def filter_o(self, **kwargs):
        qs = super(SimilarQuerySet, self).filter(**kwargs)
        for lookup, query in kwargs.items():
            if lookup.endswith('__similar'):
                field = lookup[:-9]
                select = {'%s_similarity' % field: "similarity(%s, '%s')" % (field, query)}
                qs = qs.extra(select=select)
                # TODO: DRY this. All the code above exactly repeats SimilarQuerySet.filter() method
                qs = qs.order_by('-%s_similarity' % field)
        return qs


class SimilarManager(Manager):
    def filter(self, *args, **kwargs):
        return self.get_queryset().filter(*args, **kwargs)

    def get_queryset(self):
        return SimilarQuerySet(self.model, using=self._db)

    def filter_o(self, *args, **kwargs):
        return self.get_queryset().filter_o(*args, **kwargs)
