import logging
import re
from typing import List

import peewee

from peewee_sanic_rest.exceptions import FilterConfigurationException, FilterInvalidArgumentException

logger = logging.getLogger(__name__)


class Filter(object):

    def __init__(self, *, ignore_failure=False):
        self.ignore_failure = ignore_failure

    def prepare_value(self, value):
        return value

    def perform_filtering(self, qs, value, context):
        raise NotImplementedError()

    def filter(self, qs, value, context=None):
        try:
            value = self.prepare_value(value)
            qs = self.perform_filtering(qs, value, context)
            assert isinstance(qs, peewee.Query), "Filter returned other type than peewee.Query"
        except FilterInvalidArgumentException:
            if not self.ignore_failure:
                raise
        return qs


class MethodFilter(Filter):

    def __init__(self, method=None, condition=None, **kwargs):
        super().__init__(**kwargs)
        self.method = method
        self.condition = condition

    def get_handler(self, context=None):
        if isinstance(self.method, str):
            method = getattr(context, self.method)
            assert method, "method '{}' not found in context '{}'".format(self.method, context)
            assert callable(method), "method '{}' must be callable".format(self.method)
            return method
        if self.method:
            raise FilterInvalidArgumentException("Method with type '{}' is not supported.".format(type(self.method)))
        return None

    def call_handler(self, qs, value, handler):
        return handler(qs, value)

    def perform_filtering(self, qs, value, context):
        handler = self.get_handler(context)
        if self.condition:
            return qs.where(self.condition)
        elif handler:
            return self.call_handler(qs, value, handler)
        raise FilterInvalidArgumentException("Both handler and condition were not found.")


class ChoiceFilter(Filter):

    def __init__(self, filters: List[Filter], **kwargs):
        super().__init__(**kwargs)
        self.filters = filters

    def perform_filtering(self, qs, value, context=None):
        for f in self.filters:
            try:
                return f.filter(qs, value, context)
            except FilterInvalidArgumentException:
                # we're passing because just one nested filter has to pass
                pass
        raise FilterInvalidArgumentException("Invalid value: '{}'.".format(value))


class RegexFilter(MethodFilter):

    def __init__(self, regex: str, **kwargs):
        super().__init__(**kwargs)
        self.regex = regex
        try:
            self._compiled = re.compile(regex)
        except re.error as e:
            raise FilterConfigurationException(e)

    @property
    def has_dict_result(self):
        return self._compiled.groups > 0

    def call_handler(self, qs, value, handler):
        if self.has_dict_result:
            return handler(qs, **value.groupdict())
        else:
            return handler(qs, value.group(0))

    def prepare_value(self, value):
        match = self._compiled.match(value)
        if not match:
            raise FilterInvalidArgumentException("Value '{}' not matches regex '{}'.".format(value, self.regex))
        return match


class TypeFilter(MethodFilter):

    type = None

    def prepare_value(self, value):
        try:
            return self.type(value)
        except Exception as e:
            raise FilterInvalidArgumentException("Value '{}' not coercible to '{}'.".format(value, self.type)) from e


class IntegerFilter(TypeFilter):
    type = int


class FloatFilter(TypeFilter):
    type = float


class StringFilter(TypeFilter):
    type = str


class CSVFilter(MethodFilter):

    def __init__(self, inner_filter: Filter=None, **kwargs):
        super().__init__(**kwargs)
        self.inner_filter = inner_filter or StringFilter()

    def prepare_value(self, value):
        try:
            values = value.split(',')
            return [self.inner_filter.prepare_value(val) for val in values]
        except (AttributeError, ValueError) as e:
            raise FilterInvalidArgumentException("Value '{}' is not proper CSV.".format(value)) from e


class FilterSet(Filter):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.filters = self._find_filters()

    def _find_filters(self):
        filters = {}
        for name in dir(self):
            if name.startswith('_'):
                continue
            attr = getattr(self, name)
            if isinstance(attr, Filter):
                filters[name] = attr
        return filters

    def prepare_value(self, value):
        if not isinstance(value, dict):
            raise FilterInvalidArgumentException("Invalid value. Should be dict, found '{}'.".format(value))
        return {k: v if isinstance(v, list) else [v] for k, v in value.items()}

    def perform_filtering(self, qs, value, context):
        for name, filter in self.filters.items():
            # if filter is FilterSet, we should pass the same value as we received
            filter_args = [value] if isinstance(filter, FilterSet) else value.get(name, [])
            for arg in filter_args:
                try:
                    qs = filter.filter(qs, arg, context=self)
                except FilterInvalidArgumentException as e:
                    if not self.ignore_failure:
                        raise FilterInvalidArgumentException("Filter '{}' raised error!".format(name)) from e
        return qs


class FilteredResourceMixin(FilterSet):

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = self.filter(qs, request.args)
        return qs
