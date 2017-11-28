import logging

from sanic.exceptions import abort, InvalidUsage
from sanic.response import json

from peewee_sanic_rest.filters import FilteredResourceMixin
from peewee_sanic_rest.exceptions import FilterInvalidArgumentException, ConfigurationException

logger = logging.getLogger(__name__)


def detail_route(**kw):
    def inner(f):
        setattr(f, '_route', {'type': 'detail', 'kwargs': kw})
        return f
    return inner


def index_route(**kw):
    def inner(f):
        setattr(f, '_route', {'type': 'index', 'kwargs': kw})
        return f
    return inner


class ListModelMixin(object):

    PAGE_ITEMS_LIMIT_DEFAULT = 20
    PAGE_ITEMS_LIMIT_MAX = 100

    def get_page_and_limit(self, request):
        try:
            page = int(request.args.get('page', 1))
            limit = min(int(request.args.get('limit', self.PAGE_ITEMS_LIMIT_DEFAULT)), self.PAGE_ITEMS_LIMIT_MAX)
            return page, limit
        except (KeyError, TypeError, ValueError):
            raise InvalidUsage("Page and limit parameters should be a number.")

    async def get_total(self, request, queryset):
        return await self.manager.count(queryset)

    async def list(self, request):
        queryset = self.get_queryset(request)
        page, limit = self.get_page_and_limit(request)
        paginated_queryset = queryset.paginate(page, limit)
        objects = await self.manager.execute(paginated_queryset)
        results = []
        for o in objects:
            results.append(await self.serialize(o))
        return json({
            'results': results,
            'page': page,
            'limit': limit,
            'total': await self.get_total(request, queryset)
        })


class CreateModelMixin(object):

    async def create(self, request):
        errors = self.schema.validate(request.json)
        if not errors:
            obj = await self.perform_create(request.json)
            return json(await self.serialize(obj))
        else:
            return json(errors, status=400)

    async def perform_create(self, data):
        return await self.manager.create(self.model, **data)


class RetrieveModelMixin(object):

    async def retrieve(self, request, id):
        obj = await self.get_object(request, id)
        return json(await self.serialize(obj))

    async def get_object(self, request, id):
        return await self.manager.get(self.get_queryset(request), id=id)


class DeleteModelMixin(object):

    async def delete(self, request, id):
        obj = await self.manager.get(self.get_queryset(request), id=id)
        success = await self.perform_delete(obj)
        status = 200 if success else 400
        message = 'success' if success else 'failure'
        return json({'result': message}, status=status)

    async def perform_delete(self, obj):
        return await self.manager.delete(obj, recursive=True)


class UpdateModelMixin(object):

    async def update(self, request, id):
        errors = self.schema.validate(request.json, partial=True)
        if not errors:
            obj = await self.manager.get(self.model, id=id)
            for k, v in request.json.items():
                setattr(obj, k, v)
            updated = await self.manager.update(obj)
            if updated:
                return json(await self.serialize(obj))
            else:
                return json({'result': 'no record updated'}, status=400)
        else:
            return json(errors, status=400)


class ModelResource(object):

    schema_model = None
    model = None
    queryset = None

    action_to_handler = {
        'list_get': 'list',
        'list_post': 'create',
        'detail_get': 'retrieve',
        'detail_delete': 'delete',
        'detail_patch': 'update'
    }

    def get_queryset(self, request):
        return self.queryset if self.queryset is not None else self.model.select()

    def get_schema_model(self, request):
        return self.schema_model()

    async def serialize(self, o):
        return self.schema.dump(o).data

    async def dispatch(self, request, id=None):
        try:
            return await self._call_action(request, id)
        except self.model.DoesNotExist:
            return json({'error': 'Not Found'}, status=404)
        except FilterInvalidArgumentException as e:
            logger.exception(e)
            return json({'error': str(e)}, status=400)

    async def _call_action(self, request, id):
        is_detail_view = bool(id)
        handler = self._get_handler(request.method, is_detail_view)
        if is_detail_view:
            return await handler(request, id)
        else:
            return await handler(request)

    def _get_handler(self, method, is_detail_view):
        try:
            handler_name = '{}_{}'.format('detail' if is_detail_view else 'list', method.lower())
            action_name = self.action_to_handler[handler_name]
            return getattr(self, action_name)
        except (AttributeError, KeyError):
            abort(405)

    @classmethod
    def as_view(cls, manager, method='dispatch'):
        def view(request, *args, **kwargs):
            self = cls()
            self.schema = self.get_schema_model(request)
            self.request = request
            self.manager = manager
            self.args = args
            self.kwargs = kwargs
            handler = getattr(self, method)
            return handler(request, *args, **kwargs)
        return view

    @classmethod
    def register(cls, app, manager, **kwargs):
        app.add_route(cls.as_view(manager), '/', methods=['GET', 'POST'])
        app.add_route(cls.as_view(manager), '/<id:number>', methods=['GET', 'PATCH', 'DELETE'])
        for name in dir(cls):
            elem = getattr(cls, name)
            route = getattr(elem, '_route', None)
            if route:
                cls.add_custom_route(app, manager, name, route)

    @classmethod
    def add_custom_route(cls, app, manager, name, route):
        endpoint = name.replace('_', '-')
        handler = cls.as_view(method=name, manager=manager)
        if route['type'] == 'detail':
            path = '/<id:number>/{}'.format(endpoint)
            app.add_route(handler, path, **route['kwargs'])
        elif route['type'] == 'index':
            path = '/{}'.format(endpoint)
            app.add_route(handler, path, **route['kwargs'])
        else:
            raise ConfigurationException('Unknown route type {}'.format(route['type']))


class ReadOnlyModelResource(RetrieveModelMixin, FilteredResourceMixin, ListModelMixin, ModelResource):
    pass


class GenericModelResource(CreateModelMixin, UpdateModelMixin, DeleteModelMixin, ReadOnlyModelResource):
    pass
