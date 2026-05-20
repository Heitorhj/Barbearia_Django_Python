from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta, datetime, date, time


class Servico(models.Model):
    """Serviços oferecidos pela barbearia (corte, barba, etc.)"""
    CATEGORIA_CHOICES = [
        ('cabelo', 'Cabelo'),
        ('barba', 'Barba'),
        ('combo', 'Combo'),
        ('tratamento', 'Tratamento'),
    ]

    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    preco = models.DecimalField(max_digits=8, decimal_places=2)
    duracao_minutos = models.PositiveIntegerField(default=30)
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='cabelo')
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Serviço'
        verbose_name_plural = 'Serviços'
        ordering = ['categoria', 'nome']

    def __str__(self):
        return f"{self.nome} - R$ {self.preco}"

    @property
    def duracao_display(self):
        h = self.duracao_minutos // 60
        m = self.duracao_minutos % 60
        if h and m:
            return f"{h}h {m}min"
        elif h:
            return f"{h}h"
        return f"{m}min"


class Barbeiro(models.Model):
    """Profissional da barbearia"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='barbeiro')
    telefone = models.CharField(max_length=15)
    servicos = models.ManyToManyField(Servico, related_name='barbeiros', blank=True)
    bio = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Barbeiro'
        verbose_name_plural = 'Barbeiros'

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    def get_horarios_disponiveis(self, data, servico):
        """Retorna lista de horários livres para um dia e serviço específicos"""
        horarios = []
        abertura = time(9, 0)
        fechamento = time(19, 0)
        intervalo = timedelta(minutes=30)

        # Busca agendamentos do dia
        agendamentos_dia = self.agendamentos.filter(
            data_hora__date=data,
            status__in=['pendente', 'confirmado']
        ).order_by('data_hora')

        # Gera slots do dia
        slot = datetime.combine(data, abertura)
        fim_dia = datetime.combine(data, fechamento)
        duracao = timedelta(minutes=servico.duracao_minutos)

        while slot + duracao <= fim_dia:
            slot_tz = timezone.make_aware(slot)
            fim_slot = slot_tz + duracao

            # Verifica se há conflito com agendamentos existentes
            conflito = False
            for ag in agendamentos_dia:
                fim_ag = ag.data_hora + timedelta(minutes=ag.servico.duracao_minutos)
                if not (fim_slot <= ag.data_hora or slot_tz >= fim_ag):
                    conflito = True
                    break

            # Só oferece horários futuros
            if not conflito and slot_tz > timezone.now():
                horarios.append(slot_tz)

            slot += intervalo

        return horarios


class Cliente(models.Model):
    """Perfil de cliente vinculado ao User"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cliente')
    telefone = models.CharField(max_length=15)
    data_nascimento = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    @property
    def total_agendamentos(self):
        return self.agendamentos.filter(status='concluido').count()


class Agendamento(models.Model):
    """Agendamento de um serviço na barbearia"""
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('confirmado', 'Confirmado'),
        ('concluido', 'Concluído'),
        ('cancelado', 'Cancelado'),
        ('falta', 'Falta'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='agendamentos')
    barbeiro = models.ForeignKey(Barbeiro, on_delete=models.CASCADE, related_name='agendamentos')
    servico = models.ForeignKey(Servico, on_delete=models.PROTECT, related_name='agendamentos')
    data_hora = models.DateTimeField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pendente')
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Agendamento'
        verbose_name_plural = 'Agendamentos'
        ordering = ['-data_hora']

    def __str__(self):
        return f"{self.cliente} → {self.barbeiro} | {self.servico.nome} | {self.data_hora.strftime('%d/%m/%Y %H:%M')}"

    @property
    def data_hora_fim(self):
        return self.data_hora + timedelta(minutes=self.servico.duracao_minutos)

    @property
    def pode_cancelar(self):
        """Só pode cancelar com mais de 1h de antecedência"""
        return (
            self.status in ('pendente', 'confirmado') and
            self.data_hora > timezone.now() + timedelta(hours=1)
        )

    def clean(self):
        """Valida conflito de horário para o barbeiro"""
        if not self.data_hora or not self.barbeiro_id or not self.servico_id:
            return

        fim = self.data_hora + timedelta(minutes=self.servico.duracao_minutos)

        conflitos = Agendamento.objects.filter(
            barbeiro=self.barbeiro,
            status__in=['pendente', 'confirmado'],
        ).exclude(pk=self.pk)

        for ag in conflitos:
            fim_ag = ag.data_hora + timedelta(minutes=ag.servico.duracao_minutos)
            if not (fim <= ag.data_hora or self.data_hora >= fim_ag):
                raise ValidationError(
                    f"O barbeiro já tem um agendamento nesse horário: {ag}"
                )

        # Não agendar no passado
        if self.data_hora <= timezone.now():
            raise ValidationError("Não é possível agendar em horários passados.")

        # Barbeiro deve oferecer o serviço
        if not self.barbeiro.servicos.filter(pk=self.servico_id).exists():
            raise ValidationError("Este barbeiro não realiza este serviço.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Avaliacao(models.Model):
    """Avaliação do cliente após o serviço"""
    agendamento = models.OneToOneField(Agendamento, on_delete=models.CASCADE, related_name='avaliacao')
    nota = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    comentario = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Avaliação'
        verbose_name_plural = 'Avaliações'

    def __str__(self):
        return f"{'⭐' * self.nota} – {self.agendamento.cliente}"

    def clean(self):
        try:
            agendamento = self.agendamento
        except Exception:
            return
        if agendamento.status != 'concluido':
            raise ValidationError("Só é possível avaliar agendamentos concluídos.")
