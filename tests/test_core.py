from unittest.mock import MagicMock

import pytest
from sanic.exceptions import InvalidUsage

from peewee_sanic_rest.core import ListModelMixin


def test_list_model_mixin_default_limit():
    list_model_mixin = ListModelMixin()
    request = MagicMock()
    request.args = {}
    page, limit = list_model_mixin.get_page_and_limit(request)
    assert limit == ListModelMixin.PAGE_ITEMS_LIMIT_DEFAULT


def test_list_model_mixin_bigger_than_default():
    list_model_mixin = ListModelMixin()
    request = MagicMock()
    request.args = {'limit': 55}
    page, limit = list_model_mixin.get_page_and_limit(request)
    assert limit == 55


def test_list_model_mixin_bigger_than_limit():
    list_model_mixin = ListModelMixin()
    request = MagicMock()
    more_than_max_allowed_limit = ListModelMixin.PAGE_ITEMS_LIMIT_MAX + 100
    request.args = {'limit': more_than_max_allowed_limit}
    page, limit = list_model_mixin.get_page_and_limit(request)
    assert limit == ListModelMixin.PAGE_ITEMS_LIMIT_MAX


def test_list_model_mixin_invalid_type():
    list_model_mixin = ListModelMixin()
    request = MagicMock()
    request.args = {'limit': 'one'}
    with pytest.raises(InvalidUsage):
        list_model_mixin.get_page_and_limit(request)

    request2 = MagicMock()
    request2.args = {'page': 'one'}
    with pytest.raises(InvalidUsage):
        list_model_mixin.get_page_and_limit(request2)

    request3 = MagicMock()
    request3.args = {'page': 'one', 'limit': 'one'}
    with pytest.raises(InvalidUsage):
        list_model_mixin.get_page_and_limit(request3)
