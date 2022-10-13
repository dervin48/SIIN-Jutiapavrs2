import json
import os

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.http import JsonResponse, HttpResponseRedirect
from django.template.loader import get_template
from django.urls import reverse_lazy
from django.views.generic import CreateView, FormView, DeleteView, UpdateView, View
from weasyprint import HTML, CSS

from core.pos.forms import EntradaForm, ClientForm
from core.pos.mixins import ValidatePermissionRequiredMixin, ExistsCompanyMixin
from core.pos.models import Entrada, Product, EntradaInsumo, Client
from core.reports.forms import ReportForm


class EntradaListView(ExistsCompanyMixin, ValidatePermissionRequiredMixin, FormView):
    form_class = ReportForm
    template_name = 'entrada/list.html'
    permission_required = 'view_entrada'

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            if action == 'search':
                data = []
                start_date = request.POST['start_date']
                end_date = request.POST['end_date']
                queryset = Entrada.objects.all()
                if len(start_date) and len(end_date):
                    queryset = queryset.filter(date_joined__range=[start_date, end_date])
                for i in queryset:
                    data.append(i.toJSON())
            elif action == 'search_products_detail':
                data = []
                for i in EntradaInsumo.objects.filter(entrada_id=request.POST['id']):
                    data.append(i.toJSON())
            else:
                data['error'] = 'Ha ocurrido un error'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data, safe=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Listado de Entradas'
        context['create_url'] = reverse_lazy('entrada_create')
        context['list_url'] = reverse_lazy('entrada_list')
        context['entity'] = 'Entradas'
        return context


class EntradaCreateView(ExistsCompanyMixin, ValidatePermissionRequiredMixin, CreateView):
    model = Entrada
    form_class = EntradaForm
    template_name = 'entrada/create.html'
    success_url = reverse_lazy('entrada_list')
    url_redirect = success_url
    permission_required = 'add_entrada'

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            if action == 'search_products':
                data = []
                ids_exclude = json.loads(request.POST['ids'])
                term = request.POST['term'].strip()
                products = Product.objects.filter(Q(stock__gt=0) | Q(is_inventoried=False))
                if len(term):
                    products = products.filter(name__icontains=term)
                for i in products.exclude(id__in=ids_exclude)[0:10]:
                    item = i.toJSON()
                    item['value'] = i.__str__()
                    data.append(item)
            elif action == 'search_products_select2':
                data = []
                ids_exclude = json.loads(request.POST['ids'])
                term = request.POST['term'].strip()
                data.append({'id': term, 'text': term})
                products = Product.objects.filter(name__icontains=term).filter(Q(stock__gt=0) | Q(is_inventoried=False))
                for i in products.exclude(id__in=ids_exclude)[0:10]:
                    item = i.toJSON()
                    item['text'] = i.__str__()
                    data.append(item)
            elif action == 'add':
                with transaction.atomic():
                    products = json.loads(request.POST['products'])
                    entrada = Entrada()
                    entrada.fecha_entrada = request.POST['fecha_entrada']
                    # sale.client_id = int(request.POST['client'])
                    # sale.iva = float(request.POST['iva'])
                    entrada.save()
                    for i in products:
                        detail = EntradaInsumo()
                        detail.entrada_id = entrada.id
                        detail.product_id = int(i['id'])
                        detail.cant = int(i['cant'])
                        detail.price = float(i['pvp'])
                        detail.subtotal = detail.cant * detail.price
                        detail.save()
                        if detail.product.is_inventoried:
                            detail.product.stock += detail.cant
                            detail.product.save()
                    entrada.calculate_invoice()
                    data = {'id': entrada.id}
            elif action == 'search_client':
                data = []
                term = request.POST['term']
                clients = Client.objects.filter(
                    Q(names__icontains=term) | Q(dni__icontains=term))[0:10]
                for i in clients:
                    item = i.toJSON()
                    item['text'] = i.get_full_name()
                    data.append(item)
            elif action == 'create_client':
                with transaction.atomic():
                    form = ClientForm(request.POST)
                    data = form.save()
            else:
                data['error'] = 'No ha ingresado a ninguna opción'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data, safe=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Creación de una Entrada'
        context['entity'] = 'Entradas'
        context['list_url'] = self.success_url
        context['action'] = 'add'
        context['products'] = []
        # context['frmClient'] = ClientForm()
        return context


class EntradaUpdateView(ExistsCompanyMixin, ValidatePermissionRequiredMixin, UpdateView):
    model = Entrada
    form_class = EntradaForm
    template_name = 'entrada/create.html'
    success_url = reverse_lazy('entrada_list')
    url_redirect = success_url
    permission_required = 'change_entrada'

    def get_form(self, form_class=None):
        instance = self.get_object()
        form = EntradaForm(instance=instance)
        form.fields['client'].queryset = Client.objects.filter(id=instance.client.id)
        return form

    def get_details_product(self):
        data = []
        entrada = self.get_object()
        for i in entrada.entradainsumo_set.all():
            item = i.product.toJSON()
            item['cant'] = i.cant
            data.append(item)
        return json.dumps(data)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            if action == 'search_products':
                data = []
                ids_exclude = json.loads(request.POST['ids'])
                term = request.POST['term'].strip()
                products = Product.objects.filter(Q(stock__gt=0) | Q(is_inventoried=False))
                if len(term):
                    products = products.filter(name__icontains=term)
                for i in products.exclude(id__in=ids_exclude)[0:10]:
                    item = i.toJSON()
                    item['value'] = i.__str__()
                    data.append(item)
            elif action == 'search_products_select2':
                data = []
                ids_exclude = json.loads(request.POST['ids'])
                term = request.POST['term'].strip()
                data.append({'id': term, 'text': term})
                products = Product.objects.filter(name__icontains=term).filter(Q(stock__gt=0) | Q(is_inventoried=False))
                for i in products.exclude(id__in=ids_exclude)[0:10]:
                    item = i.toJSON()
                    item['text'] = i.__str__()
                    data.append(item)
            elif action == 'edit':
                with transaction.atomic():
                    with transaction.atomic():
                        products = json.loads(request.POST['products'])
                        entrada = self.get_object()
                        entrada.fecha_entrada = request.POST['fecha_entrada']
                        # sale.client_id = int(request.POST['client'])
                        # sale.iva = float(request.POST['iva'])
                        entrada.save()
                        entrada.entradainsumo_set.all().delete()
                        for i in products:
                            detail = EntradaInsumo()
                            detail.entrada_id = entrada.id
                            detail.product_id = int(i['id'])
                            detail.cant = int(i['cant'])
                            detail.price = float(i['pvp'])
                            # detail.subtotal = detail.cant * detail.price
                            detail.save()
                            if detail.product.is_inventoried:
                                detail.product.stock += detail.cant
                                detail.product.save()
                        entrada.calculate_invoice()
                        data = {'id': entrada.id}
                    data = {'id': entrada.id}
            elif action == 'search_client':
                data = []
                term = request.POST['term']
                clients = Client.objects.filter(
                    Q(names__icontains=term) | Q(dni__icontains=term))[0:10]
                for i in clients:
                    item = i.toJSON()
                    item['text'] = i.get_full_name()
                    data.append(item)
            elif action == 'create_client':
                with transaction.atomic():
                    form = ClientForm(request.POST)
                    data = form.save()
            else:
                data['error'] = 'No ha ingresado a ninguna opción'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data, safe=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edición de una Entrada'
        context['entity'] = 'Entradas'
        context['list_url'] = self.success_url
        context['action'] = 'edit'
        context['products'] = self.get_details_product()
        # context['frmClient'] = ClientForm()
        return context


class EntradaDeleteView(ExistsCompanyMixin, ValidatePermissionRequiredMixin, DeleteView):
    model = Entrada
    template_name = 'entrada/delete.html'
    success_url = reverse_lazy('entrada_list')
    url_redirect = success_url
    permission_required = 'delete_entrada'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            self.object.delete()
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Eliminación de una Entrada'
        context['entity'] = 'Entradas'
        context['list_url'] = self.success_url
        return context


class EntradaInvoicePdfView(LoginRequiredMixin, View):

    def get(self, request, *args, **kwargs):
        try:
            template = get_template('entrada/invoice.html')
            context = {
                'entrada': Entrada.objects.get(pk=self.kwargs['pk']),
                'icon': f'{settings.MEDIA_URL}logo.png'
            }
            html = template.render(context)
            css_url = os.path.join(settings.BASE_DIR, 'static/lib/bootstrap-4.6.0/css/bootstrap.min.css')
            pdf = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf(stylesheets=[CSS(css_url)])
            return HttpResponse(pdf, content_type='application/pdf')
        except:
            pass
        return HttpResponseRedirect(reverse_lazy('entrada_list'))
