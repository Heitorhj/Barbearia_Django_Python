from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.utils import timezone
from django.db.models import Avg, Count
from datetime import datetime

from .models import Agendamento, Servico, Barbeiro, Cliente, Avaliacao
from .forms import (
    RegistroClienteForm, AgendamentoStep1Form, AgendamentoStep2Form,
    AgendamentoStep3Form, CancelarAgendamentoForm, AvaliacaoForm
)


# ─── Registro ────────────────────────────────────────────────────────────────

def registro(request):
    if request.user.is_authenticated:
        return redirect('meus_agendamentos')

    form = RegistroClienteForm(request.POST or None)
    if form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Conta criada com sucesso! Bem-vindo!")
        return redirect('meus_agendamentos')

    return render(request, 'agendamentos/registro.html', {'form': form})


# ─── Página inicial ───────────────────────────────────────────────────────────

def home(request):
    servicos = Servico.objects.filter(ativo=True)[:6]
    barbeiros = Barbeiro.objects.filter(ativo=True).annotate(
        media_nota=Avg('agendamentos__avaliacao__nota'),
        total_servicos=Count('agendamentos__avaliacao')
    )
    avaliacoes_recentes = Avaliacao.objects.select_related(
        'agendamento__cliente__user', 'agendamento__barbeiro__user'
    ).order_by('-criado_em')[:5]

    return render(request, 'agendamentos/home.html', {
        'servicos': servicos,
        'barbeiros': barbeiros,
        'avaliacoes_recentes': avaliacoes_recentes,
    })


# ─── Agendamento wizard (3 passos) ────────────────────────────────────────────

@login_required
def agendar_step1(request):
    """Escolhe serviço e barbeiro"""
    # Garante que o user tem perfil de cliente
    if not hasattr(request.user, 'cliente'):
        messages.error(request, "Seu perfil de cliente não foi encontrado.")
        return redirect('home')

    form = AgendamentoStep1Form(request.POST or None)
    if form.is_valid():
        request.session['ag_servico_id'] = form.cleaned_data['servico'].pk
        request.session['ag_barbeiro_id'] = form.cleaned_data['barbeiro'].pk
        return redirect('agendar_step2')

    return render(request, 'agendamentos/agendar_step1.html', {'form': form})


@login_required
def agendar_step2(request):
    """Escolhe data"""
    if 'ag_servico_id' not in request.session:
        return redirect('agendar_step1')

    form = AgendamentoStep2Form(request.POST or None)
    if form.is_valid():
        request.session['ag_data'] = form.cleaned_data['data'].isoformat()
        return redirect('agendar_step3')

    return render(request, 'agendamentos/agendar_step2.html', {'form': form})


@login_required
def agendar_step3(request):
    """Escolhe horário e confirma"""
    servico_id = request.session.get('ag_servico_id')
    barbeiro_id = request.session.get('ag_barbeiro_id')
    data_str = request.session.get('ag_data')

    if not all([servico_id, barbeiro_id, data_str]):
        return redirect('agendar_step1')

    servico = get_object_or_404(Servico, pk=servico_id)
    barbeiro = get_object_or_404(Barbeiro, pk=barbeiro_id)
    data = datetime.fromisoformat(data_str).date()

    horarios = barbeiro.get_horarios_disponiveis(data, servico)

    form = AgendamentoStep3Form(request.POST or None, horarios=horarios)

    if not horarios:
        messages.warning(request, "Não há horários disponíveis para esta data. Escolha outra.")

    if form.is_valid():
        horario = datetime.fromisoformat(form.cleaned_data['horario'])
        horario_aware = timezone.make_aware(horario) if timezone.is_naive(horario) else horario

        agendamento = Agendamento(
            cliente=request.user.cliente,
            barbeiro=barbeiro,
            servico=servico,
            data_hora=horario_aware,
        )
        try:
            agendamento.save()
            # Limpa sessão
            for k in ('ag_servico_id', 'ag_barbeiro_id', 'ag_data'):
                request.session.pop(k, None)
            messages.success(request, "Agendamento realizado com sucesso!")
            return redirect('detalhe_agendamento', pk=agendamento.pk)
        except Exception as e:
            messages.error(request, f"Erro ao agendar: {e}")

    return render(request, 'agendamentos/agendar_step3.html', {
        'form': form,
        'servico': servico,
        'barbeiro': barbeiro,
        'data': data,
        'horarios': horarios,
    })


# ─── Meus agendamentos ────────────────────────────────────────────────────────

@login_required
def meus_agendamentos(request):
    if not hasattr(request.user, 'cliente'):
        messages.error(request, "Perfil de cliente não encontrado.")
        return redirect('home')

    agendamentos = request.user.cliente.agendamentos.select_related(
        'servico', 'barbeiro__user'
    ).order_by('data_hora')

    proximos = agendamentos.filter(
        data_hora__gte=timezone.now(),
        status__in=['pendente', 'confirmado']
    )
    historico = agendamentos.filter(
        status__in=['concluido', 'cancelado', 'falta']
    )

    return render(request, 'agendamentos/meus_agendamentos.html', {
        'proximos': proximos,
        'historico': historico,
    })


@login_required
def detalhe_agendamento(request, pk):
    agendamento = get_object_or_404(
        Agendamento, pk=pk, cliente=request.user.cliente
    )
    avaliacao = getattr(agendamento, 'avaliacao', None)

    return render(request, 'agendamentos/detalhe_agendamento.html', {
        'agendamento': agendamento,
        'avaliacao': avaliacao,
    })


@login_required
def cancelar_agendamento(request, pk):
    agendamento = get_object_or_404(
        Agendamento, pk=pk, cliente=request.user.cliente
    )

    if not agendamento.pode_cancelar:
        messages.error(request, "Este agendamento não pode ser cancelado.")
        return redirect('detalhe_agendamento', pk=pk)

    form = CancelarAgendamentoForm(request.POST or None)
    if form.is_valid():
        agendamento.status = 'cancelado'
        agendamento.save()
        messages.success(request, "Agendamento cancelado.")
        return redirect('meus_agendamentos')

    return render(request, 'agendamentos/cancelar.html', {
        'agendamento': agendamento,
        'form': form,
    })


@login_required
def avaliar_agendamento(request, pk):
    agendamento = get_object_or_404(
        Agendamento, pk=pk, cliente=request.user.cliente, status='concluido'
    )

    if hasattr(agendamento, 'avaliacao'):
        messages.info(request, "Você já avaliou este agendamento.")
        return redirect('detalhe_agendamento', pk=pk)

    form = AvaliacaoForm(request.POST or None)
    if form.is_valid():
        avaliacao = form.save(commit=False)
        avaliacao.agendamento = agendamento
        avaliacao.save()
        messages.success(request, "Obrigado pela sua avaliação!")
        return redirect('detalhe_agendamento', pk=pk)

    return render(request, 'agendamentos/avaliar.html', {
        'agendamento': agendamento,
        'form': form,
    })


# ─── Serviços (público) ───────────────────────────────────────────────────────

def lista_servicos(request):
    servicos = Servico.objects.filter(ativo=True).order_by('categoria', 'preco')
    return render(request, 'agendamentos/servicos.html', {'servicos': servicos})


# ─── Dashboard barbeiro ───────────────────────────────────────────────────────

@login_required
def dashboard_barbeiro(request):
    if not hasattr(request.user, 'barbeiro'):
        messages.error(request, "Acesso restrito a barbeiros.")
        return redirect('home')

    barbeiro = request.user.barbeiro
    hoje = timezone.now().date()

    agendamentos_hoje = barbeiro.agendamentos.filter(
        data_hora__date=hoje,
        status__in=['pendente', 'confirmado']
    ).order_by('data_hora')

    proximos_7_dias = barbeiro.agendamentos.filter(
        data_hora__date__gt=hoje,
        data_hora__date__lte=hoje + timezone.timedelta(days=7),
        status__in=['pendente', 'confirmado']
    ).order_by('data_hora')

    stats = {
        'total_mes': barbeiro.agendamentos.filter(
            data_hora__month=hoje.month, status='concluido'
        ).count(),
        'media_nota': barbeiro.agendamentos.aggregate(
            m=Avg('avaliacao__nota')
        )['m'],
    }

    return render(request, 'agendamentos/dashboard_barbeiro.html', {
        'barbeiro': barbeiro,
        'agendamentos_hoje': agendamentos_hoje,
        'proximos_7_dias': proximos_7_dias,
        'stats': stats,
    })
