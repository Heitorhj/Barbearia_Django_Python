from django.contrib import admin
from django.utils.html import format_html
from .models import Servico, Barbeiro, Cliente, Agendamento, Avaliacao


@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'categoria', 'preco', 'duracao_minutos', 'ativo')
    list_filter = ('categoria', 'ativo')
    search_fields = ('nome',)
    list_editable = ('preco', 'ativo')


@admin.register(Barbeiro)
class BarbeiroAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'telefone', 'ativo')
    list_filter = ('ativo',)
    filter_horizontal = ('servicos',)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'telefone', 'total_agendamentos')
    search_fields = ('user__first_name', 'user__last_name', 'user__email')


@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'barbeiro', 'servico', 'data_hora', 'status_badge')
    list_filter = ('status', 'barbeiro', 'servico')
    search_fields = ('cliente__user__first_name', 'cliente__user__last_name')
    date_hierarchy = 'data_hora'
    readonly_fields = ('criado_em', 'atualizado_em')

    def status_badge(self, obj):
        cores = {
            'pendente': '#f59e0b',
            'confirmado': '#3b82f6',
            'concluido': '#10b981',
            'cancelado': '#ef4444',
            'falta': '#6b7280',
        }
        cor = cores.get(obj.status, '#000')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px">{}</span>',
            cor, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    actions = ['confirmar_agendamentos', 'concluir_agendamentos']

    def confirmar_agendamentos(self, request, queryset):
        updated = queryset.filter(status='pendente').update(status='confirmado')
        self.message_user(request, f"{updated} agendamento(s) confirmado(s).")
    confirmar_agendamentos.short_description = "Confirmar selecionados"

    def concluir_agendamentos(self, request, queryset):
        updated = queryset.filter(status='confirmado').update(status='concluido')
        self.message_user(request, f"{updated} agendamento(s) concluído(s).")
    concluir_agendamentos.short_description = "Marcar como concluído"


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ('agendamento', 'nota', 'criado_em')
    list_filter = ('nota',)
