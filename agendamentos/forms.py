from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from .models import Agendamento, Avaliacao, Cliente, Servico, Barbeiro
from datetime import date


class RegistroClienteForm(UserCreationForm):
    """Cadastro de novo cliente"""
    first_name = forms.CharField(label='Nome', max_length=50)
    last_name = forms.CharField(label='Sobrenome', max_length=50)
    email = forms.EmailField(label='E-mail')
    telefone = forms.CharField(label='Telefone', max_length=15)
    data_nascimento = forms.DateField(
        label='Data de nascimento',
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'telefone',
                  'data_nascimento', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            Cliente.objects.create(
                user=user,
                telefone=self.cleaned_data['telefone'],
                data_nascimento=self.cleaned_data.get('data_nascimento'),
            )
        return user


class AgendamentoStep1Form(forms.Form):
    """Passo 1: escolher serviço e barbeiro"""
    servico = forms.ModelChoiceField(
        queryset=Servico.objects.filter(ativo=True),
        label='Serviço',
        empty_label='Selecione um serviço'
    )
    barbeiro = forms.ModelChoiceField(
        queryset=Barbeiro.objects.filter(ativo=True),
        label='Barbeiro',
        empty_label='Selecione um barbeiro'
    )

    def clean(self):
        cleaned = super().clean()
        servico = cleaned.get('servico')
        barbeiro = cleaned.get('barbeiro')
        if servico and barbeiro:
            if not barbeiro.servicos.filter(pk=servico.pk).exists():
                raise forms.ValidationError(
                    "Este barbeiro não realiza o serviço selecionado."
                )
        return cleaned


class AgendamentoStep2Form(forms.Form):
    """Passo 2: escolher data"""
    data = forms.DateField(
        label='Data',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def clean_data(self):
        d = self.cleaned_data['data']
        if d < date.today():
            raise forms.ValidationError("Escolha uma data futura.")
        if d.weekday() == 6:  # domingo
            raise forms.ValidationError("A barbearia não funciona aos domingos.")
        return d


class AgendamentoStep3Form(forms.Form):
    """Passo 3: escolher horário"""
    horario = forms.ChoiceField(label='Horário disponível')

    def __init__(self, *args, horarios=None, **kwargs):
        super().__init__(*args, **kwargs)
        if horarios:
            self.fields['horario'].choices = [
                (h.isoformat(), h.strftime('%H:%M')) for h in horarios
            ]
        else:
            self.fields['horario'].choices = []


class CancelarAgendamentoForm(forms.Form):
    """Confirmação de cancelamento"""
    confirmar = forms.BooleanField(
        label='Confirmo o cancelamento deste agendamento',
        required=True
    )


class AvaliacaoForm(forms.ModelForm):
    class Meta:
        model = Avaliacao
        fields = ['nota', 'comentario']
        widgets = {
            'nota': forms.RadioSelect(),
            'comentario': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Conte como foi sua experiência...'}),
        }
        labels = {
            'nota': 'Sua nota (1 a 5)',
            'comentario': 'Comentário (opcional)',
        }
