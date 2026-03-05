import os
import re
from datetime import datetime, date
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, send_file, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from io import BytesIO
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from dotenv import load_dotenv
import json

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tire-management-secret-key-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'tire_management.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== MODELOS ====================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

class Carro(db.Model):
    __tablename__ = 'carros'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    numero = db.Column(db.String(20), nullable=False)
    piloto = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50), default='Stock Car')
    status = db.Column(db.String(20), default='Ativo')
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    pneus = db.relationship('Pneu', backref='carro', lazy=True)

class Pista(db.Model):
    __tablename__ = 'pistas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), unique=True, nullable=False)
    km_por_volta = db.Column(db.Float, nullable=False)
    localizacao = db.Column(db.String(100), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

class Pneu(db.Model):
    __tablename__ = 'pneus'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
    codigo_barras = db.Column(db.String(50), unique=True, nullable=False)
    carro_id = db.Column(db.Integer, db.ForeignKey('carros.id'), nullable=False)
    status = db.Column(db.String(20), default='Disponível')  # Disponível, Montado, Descartado
    condicao = db.Column(db.String(20), default='Novo')  # Novo, Usado
    quilometragem_atual = db.Column(db.Float, default=0.0)
    profundidade_inicial = db.Column(db.Float, nullable=False)
    limite_km = db.Column(db.Integer, default=1000)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    medicoes = db.relationship('Medicao', backref='pneu', lazy=True)

class Medicao(db.Model):
    __tablename__ = 'medicoes'
    id = db.Column(db.Integer, primary_key=True)
    pneu_id = db.Column(db.Integer, db.ForeignKey('pneus.id'), nullable=False)
    data_medicao = db.Column(db.DateTime, default=datetime.utcnow)
    tipo_evento = db.Column(db.String(50), nullable=False)  # Treino, Classificação, Corrida
    voltas = db.Column(db.Integer, nullable=False)
    tempo_pista = db.Column(db.Integer, nullable=False)  # minutos
    pista_nome = db.Column(db.String(150), nullable=False)
    quilometragem = db.Column(db.Float, nullable=False)
    km_total = db.Column(db.Float, nullable=False)

    # Profundidades
    interno = db.Column(db.Float, nullable=False)
    centro_interno = db.Column(db.Float, nullable=False)
    centro_externo = db.Column(db.Float, nullable=False)
    externo = db.Column(db.Float, nullable=False)
    profundidade_media = db.Column(db.Float, nullable=False)

    # Condições
    condicao_twi = db.Column(db.String(20), nullable=False)  # ok, alerta, crítico
    condicao_km = db.Column(db.String(20), nullable=False)
    acao = db.Column(db.String(20), nullable=False)  # continuar, atenção, descartar

class SetPneus(db.Model):
    __tablename__ = 'sets_pneus'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    carro_id = db.Column(db.Integer, db.ForeignKey('carros.id'), nullable=False)
    data_montagem = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Ativo')  # Ativo, Desmontado

    pneu_dianteiro_esquerdo_id = db.Column(db.Integer, db.ForeignKey('pneus.id'))
    pneu_dianteiro_direito_id = db.Column(db.Integer, db.ForeignKey('pneus.id'))
    pneu_traseiro_esquerdo_id = db.Column(db.Integer, db.ForeignKey('pneus.id'))
    pneu_traseiro_direito_id = db.Column(db.Integer, db.ForeignKey('pneus.id'))

    carro = db.relationship('Carro', backref='sets')
    pneu_de = db.relationship('Pneu', foreign_keys=[pneu_dianteiro_esquerdo_id])
    pneu_dd = db.relationship('Pneu', foreign_keys=[pneu_dianteiro_direito_id])
    pneu_te = db.relationship('Pneu', foreign_keys=[pneu_traseiro_esquerdo_id])
    pneu_td = db.relationship('Pneu', foreign_keys=[pneu_traseiro_direito_id])

# ==================== FUNÇÕES AUXILIARES ====================

def is_logged_in():
    return session.get('user_logged_in') is True

@app.context_processor
def inject_globals():
    return {
        'current_year': datetime.now().year
    }

# ==================== ROTAS PÚBLICAS ====================

@app.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('login'))

    # Estatísticas gerais
    total_pneus = Pneu.query.count()
    total_medicoes = Medicao.query.count()
    total_carros = Carro.query.filter_by(status='Ativo').count()

    # Pneus por status
    pneus_disponiveis = Pneu.query.filter_by(status='Disponível').count()
    pneus_montados = Pneu.query.filter_by(status='Montado').count()
    pneus_novos = Pneu.query.filter_by(condicao='Novo').count()
    pneus_usados = Pneu.query.filter_by(condicao='Usado').count()

    # Buscar todos os pneus (exceto descartados) com informações detalhadas
    pneus = Pneu.query.filter(Pneu.status != 'Descartado').order_by(Pneu.nome).all()

    pneus_detalhados = []
    for pneu in pneus:
        # Última medição
        ultima_medicao = Medicao.query.filter_by(pneu_id=pneu.id).order_by(Medicao.data_medicao.desc()).first()

        # Total de voltas (soma de todas as medições)
        total_voltas = db.session.query(db.func.sum(Medicao.voltas)).filter_by(pneu_id=pneu.id).scalar() or 0

        # Posição atual no carro (se estiver montado)
        posicao_atual = None
        set_nome = None
        if pneu.status == 'Montado':
            # Buscar em qual set está montado
            set_ativo = SetPneus.query.filter(
                db.or_(
                    SetPneus.pneu_dianteiro_esquerdo_id == pneu.id,
                    SetPneus.pneu_dianteiro_direito_id == pneu.id,
                    SetPneus.pneu_traseiro_esquerdo_id == pneu.id,
                    SetPneus.pneu_traseiro_direito_id == pneu.id
                ),
                SetPneus.status == 'Ativo'
            ).first()

            if set_ativo:
                set_nome = set_ativo.nome
                if set_ativo.pneu_dianteiro_esquerdo_id == pneu.id:
                    posicao_atual = 'DE'
                elif set_ativo.pneu_dianteiro_direito_id == pneu.id:
                    posicao_atual = 'DD'
                elif set_ativo.pneu_traseiro_esquerdo_id == pneu.id:
                    posicao_atual = 'TE'
                elif set_ativo.pneu_traseiro_direito_id == pneu.id:
                    posicao_atual = 'TD'

        pneus_detalhados.append({
            'pneu': pneu,
            'ultima_medicao': ultima_medicao,
            'total_voltas': total_voltas,
            'posicao_atual': posicao_atual,
            'set_nome': set_nome
        })

    stats = {
        'total_pneus': total_pneus,
        'total_medicoes': total_medicoes,
        'total_carros': total_carros,
        'pneus_disponiveis': pneus_disponiveis,
        'pneus_montados': pneus_montados,
        'pneus_novos': pneus_novos,
        'pneus_usados': pneus_usados
    }

    return render_template('index.html', stats=stats, pneus_detalhados=pneus_detalhados)

# ==================== LOGIN/LOGOUT ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Credenciais inválidas.', 'danger')
            return render_template('login.html')

        session['user_logged_in'] = True
        session['user_id'] = user.id
        session['username'] = user.username

        flash('Login realizado com sucesso!', 'success')
        return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso.', 'success')
    return redirect(url_for('login'))

# ==================== ROTAS - COMPRAR PNEUS ====================

@app.route('/pneus/comprar', methods=['GET', 'POST'])
def comprar_pneus():
    if not is_logged_in():
        return redirect(url_for('login'))

    carros = Carro.query.filter_by(status='Ativo').all()

    if request.method == 'POST':
        quantidade = int(request.form.get('quantidade', 1))
        carro_id = int(request.form.get('carro_id'))
        prefixo = request.form.get('prefixo', 'P')
        inicio_numeracao = int(request.form.get('inicio_numeracao', 1))
        prof_inicial = float(request.form.get('profundidade_inicial', 8.0))
        limite_km = int(request.form.get('limite_km', 1000))

        # Criar pneus
        for i in range(quantidade):
            nome_pneu = f"{prefixo}{(inicio_numeracao + i):03d}"
            codigo_barras = f"{datetime.now().year}{(inicio_numeracao + i):05d}"

            novo_pneu = Pneu(
                nome=nome_pneu,
                codigo_barras=codigo_barras,
                carro_id=carro_id,
                status='Disponível',
                condicao='Novo',
                quilometragem_atual=0.0,
                profundidade_inicial=prof_inicial,
                limite_km=limite_km
            )
            db.session.add(novo_pneu)

        db.session.commit()
        flash(f'{quantidade} pneu(s) adicionado(s) com sucesso!', 'success')
        return redirect(url_for('comprar_pneus'))

    return render_template('comprar_pneus.html', carros=carros)

# ==================== ROTAS - CARROS ====================

@app.route('/carros', methods=['GET', 'POST'])
def carros():
    if not is_logged_in():
        return redirect(url_for('login'))

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        numero = request.form.get('numero', '').strip()
        piloto = request.form.get('piloto', '').strip()
        categoria = request.form.get('categoria', 'Stock Car').strip()

        if not nome or not numero or not piloto:
            flash('Preencha todos os campos obrigatórios!', 'danger')
            return redirect(url_for('carros'))

        if Carro.query.filter_by(nome=nome).first():
            flash('Já existe um carro com este nome!', 'danger')
            return redirect(url_for('carros'))

        novo_carro = Carro(
            nome=nome,
            numero=numero,
            piloto=piloto,
            categoria=categoria,
            status='Ativo'
        )
        db.session.add(novo_carro)
        db.session.commit()

        flash(f'Carro {nome} cadastrado com sucesso!', 'success')
        return redirect(url_for('carros'))

    carros_lista = Carro.query.order_by(Carro.nome).all()
    return render_template('carros.html', carros=carros_lista)

@app.route('/carros/<int:carro_id>/editar', methods=['POST'])
def editar_carro(carro_id):
    if not is_logged_in():
        return redirect(url_for('login'))

    carro = Carro.query.get_or_404(carro_id)
    carro.numero = request.form.get('numero', carro.numero).strip()
    carro.piloto = request.form.get('piloto', carro.piloto).strip()
    carro.status = request.form.get('status', carro.status).strip()

    db.session.commit()
    flash(f'Carro {carro.nome} atualizado!', 'success')
    return redirect(url_for('carros'))

@app.route('/carros/<int:carro_id>/remover', methods=['POST'])
def remover_carro(carro_id):
    if not is_logged_in():
        return redirect(url_for('login'))

    carro = Carro.query.get_or_404(carro_id)

    # Verificar se tem pneus vinculados
    pneus_vinculados = Pneu.query.filter_by(carro_id=carro_id).count()
    if pneus_vinculados > 0:
        flash(f'Não é possível remover! {pneus_vinculados} pneu(s) vinculado(s).', 'danger')
        return redirect(url_for('carros'))

    db.session.delete(carro)
    db.session.commit()

    flash(f'Carro {carro.nome} removido!', 'success')
    return redirect(url_for('carros'))

# ==================== ROTAS - PISTAS ====================

@app.route('/pistas', methods=['GET', 'POST'])
def pistas():
    if not is_logged_in():
        return redirect(url_for('login'))

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        km_por_volta = float(request.form.get('km_por_volta', 0))
        localizacao = request.form.get('localizacao', '').strip()

        if not nome or km_por_volta <= 0 or not localizacao:
            flash('Preencha todos os campos corretamente!', 'danger')
            return redirect(url_for('pistas'))

        if Pista.query.filter_by(nome=nome).first():
            flash('Já existe uma pista com este nome!', 'danger')
            return redirect(url_for('pistas'))

        nova_pista = Pista(
            nome=nome,
            km_por_volta=km_por_volta,
            localizacao=localizacao
        )
        db.session.add(nova_pista)
        db.session.commit()

        flash(f'Pista {nome} cadastrada com sucesso!', 'success')
        return redirect(url_for('pistas'))

    pistas_lista = Pista.query.order_by(Pista.nome).all()
    return render_template('pistas.html', pistas=pistas_lista)

@app.route('/pistas/<int:pista_id>/editar', methods=['POST'])
def editar_pista(pista_id):
    if not is_logged_in():
        return redirect(url_for('login'))

    pista = Pista.query.get_or_404(pista_id)
    pista.km_por_volta = float(request.form.get('km_por_volta', pista.km_por_volta))
    pista.localizacao = request.form.get('localizacao', pista.localizacao).strip()

    db.session.commit()
    flash(f'Pista {pista.nome} atualizada!', 'success')
    return redirect(url_for('pistas'))

@app.route('/pistas/<int:pista_id>/remover', methods=['POST'])
def remover_pista(pista_id):
    if not is_logged_in():
        return redirect(url_for('login'))

    pista = Pista.query.get_or_404(pista_id)
    db.session.delete(pista)
    db.session.commit()

    flash(f'Pista {pista.nome} removida!', 'success')
    return redirect(url_for('pistas'))

# ==================== ROTAS - MEDIÇÕES ====================

@app.route('/medicoes/set', methods=['POST'])
def medicao_set():
    """Registra medição de todos os 4 pneus de um set de uma vez"""
    if not is_logged_in():
        return redirect(url_for('login'))

    try:
        # Dados gerais
        set_id = int(request.form.get('set_id'))
        tipo_evento = request.form.get('tipo_evento')
        pista_id = int(request.form.get('pista_id'))
        voltas = int(request.form.get('voltas'))

        # Buscar informações
        set_pneus = SetPneus.query.get_or_404(set_id)
        pista = Pista.query.get_or_404(pista_id)

        # Calcular quilometragem
        quilometragem = voltas * pista.km_por_volta

        # Lista de pneus do set
        pneus_dados = [
            {
                'pneu_id': set_pneus.pneu_dianteiro_esquerdo_id,
                'posicao': 'DE',
                'interno': float(request.form.get('de_interno')),
                'centro_interno': float(request.form.get('de_centro_interno')),
                'centro_externo': float(request.form.get('de_centro_externo')),
                'externo': float(request.form.get('de_externo'))
            },
            {
                'pneu_id': set_pneus.pneu_dianteiro_direito_id,
                'posicao': 'DD',
                'interno': float(request.form.get('dd_interno')),
                'centro_interno': float(request.form.get('dd_centro_interno')),
                'centro_externo': float(request.form.get('dd_centro_externo')),
                'externo': float(request.form.get('dd_externo'))
            },
            {
                'pneu_id': set_pneus.pneu_traseiro_esquerdo_id,
                'posicao': 'TE',
                'interno': float(request.form.get('te_interno')),
                'centro_interno': float(request.form.get('te_centro_interno')),
                'centro_externo': float(request.form.get('te_centro_externo')),
                'externo': float(request.form.get('te_externo'))
            },
            {
                'pneu_id': set_pneus.pneu_traseiro_direito_id,
                'posicao': 'TD',
                'interno': float(request.form.get('td_interno')),
                'centro_interno': float(request.form.get('td_centro_interno')),
                'centro_externo': float(request.form.get('td_centro_externo')),
                'externo': float(request.form.get('td_externo'))
            }
        ]

        # Registrar medição para cada pneu
        pneus_criticos = []
        pneus_alerta = []

        for dados in pneus_dados:
            if not dados['pneu_id']:
                continue

            pneu = Pneu.query.get(dados['pneu_id'])
            if not pneu:
                continue

            # Calcular médias
            profundidade_media = (
                dados['interno'] + 
                dados['centro_interno'] + 
                dados['centro_externo'] + 
                dados['externo']
            ) / 4

            km_total = pneu.quilometragem_atual + quilometragem

            # Determinar condições
            limite_km = pneu.limite_km
            condicao_km = 'ok' if km_total < limite_km * 0.8 else 'alerta' if km_total < limite_km else 'crítico'
            condicao_twi = 'ok' if profundidade_media > 2.0 else 'alerta' if profundidade_media > 1.5 else 'crítico'
            acao = 'continuar' if (condicao_km == 'ok' and condicao_twi == 'ok') else 'atenção' if (condicao_km == 'alerta' or condicao_twi == 'alerta') else 'descartar'

            # Criar medição
            nova_medicao = Medicao(
                pneu_id=pneu.id,
                tipo_evento=tipo_evento,
                voltas=voltas,
                tempo_pista=30,  # Valor padrão
                pista_nome=pista.nome,
                quilometragem=quilometragem,
                km_total=km_total,
                interno=dados['interno'],
                centro_interno=dados['centro_interno'],
                centro_externo=dados['centro_externo'],
                externo=dados['externo'],
                profundidade_media=profundidade_media,
                condicao_twi=condicao_twi,
                condicao_km=condicao_km,
                acao=acao
            )
            db.session.add(nova_medicao)

            # Atualizar pneu
            pneu.quilometragem_atual = km_total
            pneu.condicao = 'Usado'

            # Rastrear alertas
            if acao == 'descartar':
                pneus_criticos.append(f"{pneu.nome} ({dados['posicao']})")
            elif acao == 'atenção':
                pneus_alerta.append(f"{pneu.nome} ({dados['posicao']})")

        db.session.commit()

        # Mensagem de feedback
        if pneus_criticos:
            flash(f'⚠️ Medição registrada! Pneus CRÍTICOS: {", ".join(pneus_criticos)}', 'danger')
        elif pneus_alerta:
            flash(f'⚠️ Medição registrada! Pneus em ALERTA: {", ".join(pneus_alerta)}', 'warning')
        else:
            flash(f'✅ Medição do set {set_pneus.nome} registrada com sucesso! Todos os pneus OK.', 'success')

        return redirect(url_for('medicoes'))

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registrar medição: {str(e)}', 'danger')
        return redirect(url_for('medicoes'))


# ==================== ATUALIZAR ROTA DE MEDIÇÕES ORIGINAL ====================

@app.route('/medicoes', methods=['GET', 'POST'])
def medicoes():
    if not is_logged_in():
        return redirect(url_for('login'))

    # Buscar sets ativos para o novo formulário
    sets_ativos = SetPneus.query.filter_by(status='Ativo').all()

    pneus_disponiveis = Pneu.query.filter(
        Pneu.status != 'Descartado'
    ).order_by(Pneu.nome).all()

    pistas = Pista.query.order_by(Pista.nome).all()

    if request.method == 'POST':
        # Lógica da medição individual (mantém a original)
        pneu_id = int(request.form.get('pneu_id'))
        tipo_evento = request.form.get('tipo_evento')
        voltas = int(request.form.get('voltas'))
        tempo_pista = int(request.form.get('tempo_pista', 30))
        pista_id = request.form.get('pista_id')

        # Profundidades
        interno = float(request.form.get('interno'))
        centro_interno = float(request.form.get('centro_interno'))
        centro_externo = float(request.form.get('centro_externo'))
        externo = float(request.form.get('externo'))

        pneu = Pneu.query.get_or_404(pneu_id)

        # Calcular quilometragem
        if pista_id:
            pista = Pista.query.get(int(pista_id))
            quilometragem = voltas * pista.km_por_volta
            pista_nome = pista.nome
        else:
            quilometragem = float(request.form.get('quilometragem_manual', 0))
            pista_nome = request.form.get('pista_nome_manual', 'Pista não especificada')

        km_total = pneu.quilometragem_atual + quilometragem
        profundidade_media = (interno + centro_interno + centro_externo + externo) / 4

        # Determinar condições
        limite_km = pneu.limite_km
        condicao_km = 'ok' if km_total < limite_km * 0.8 else 'alerta' if km_total < limite_km else 'crítico'
        condicao_twi = 'ok' if profundidade_media > 2.0 else 'alerta' if profundidade_media > 1.5 else 'crítico'
        acao = 'continuar' if (condicao_km == 'ok' and condicao_twi == 'ok') else 'atenção' if (condicao_km == 'alerta' or condicao_twi == 'alerta') else 'descartar'

        # Criar medição
        nova_medicao = Medicao(
            pneu_id=pneu_id,
            tipo_evento=tipo_evento,
            voltas=voltas,
            tempo_pista=tempo_pista,
            pista_nome=pista_nome,
            quilometragem=quilometragem,
            km_total=km_total,
            interno=interno,
            centro_interno=centro_interno,
            centro_externo=centro_externo,
            externo=externo,
            profundidade_media=profundidade_media,
            condicao_twi=condicao_twi,
            condicao_km=condicao_km,
            acao=acao
        )
        db.session.add(nova_medicao)

        # Atualizar pneu
        pneu.quilometragem_atual = km_total
        pneu.condicao = 'Usado'

        db.session.commit()

        if acao == 'descartar':
            flash(f'⚠️ Medição registrada! Pneu {pneu.nome} em estado crítico - considere descartar.', 'danger')
        elif acao == 'atenção':
            flash(f'⚠️ Medição registrada! Pneu {pneu.nome} em alerta - monitorar de perto.', 'warning')
        else:
            flash('Medição registrada com sucesso!', 'success')

        return redirect(url_for('medicoes'))

    # Listar todas as medições
    medicoes_lista = Medicao.query.order_by(Medicao.data_medicao.desc()).all()

    return render_template('medicoes.html', 
                         pneus=pneus_disponiveis, 
                         medicoes=medicoes_lista,
                         pistas=pistas,
                         sets_ativos=sets_ativos)

# ==================== ROTAS - SETS ====================

@app.route('/sets', methods=['GET', 'POST'])
def sets():
    if not is_logged_in():
        return redirect(url_for('login'))

    if request.method == 'POST':
        nome_set = request.form.get('nome_set', '').strip()
        carro_id = int(request.form.get('carro_id'))
        pneu_de_id = request.form.get('pneu_de')
        pneu_dd_id = request.form.get('pneu_dd')
        pneu_te_id = request.form.get('pneu_te')
        pneu_td_id = request.form.get('pneu_td')

        if not nome_set:
            flash('Digite um nome para o set!', 'danger')
            return redirect(url_for('sets'))

        if not all([pneu_de_id, pneu_dd_id, pneu_te_id, pneu_td_id]):
            flash('Selecione os 4 pneus para montar o set!', 'danger')
            return redirect(url_for('sets'))

        # ✅ VALIDAÇÃO: Verificar se há pneus duplicados
        pneus_ids = [pneu_de_id, pneu_dd_id, pneu_te_id, pneu_td_id]
        if len(pneus_ids) != len(set(pneus_ids)):
            flash('❌ Erro: Você não pode usar o mesmo pneu em múltiplas posições!', 'danger')
            return redirect(url_for('sets'))

        # ✅ VALIDAÇÃO: Verificar se algum pneu já está montado em outro set
        pneus_montados = []
        for pid in pneus_ids:
            pneu = Pneu.query.get(int(pid))
            if pneu and pneu.status == 'Montado':
                pneus_montados.append(pneu.nome)

        if pneus_montados:
            flash(f'❌ Erro: Os seguintes pneus já estão montados em outro set: {", ".join(pneus_montados)}', 'danger')
            return redirect(url_for('sets'))

        # Criar set
        novo_set = SetPneus(
            nome=nome_set,
            carro_id=carro_id,
            pneu_dianteiro_esquerdo_id=int(pneu_de_id),
            pneu_dianteiro_direito_id=int(pneu_dd_id),
            pneu_traseiro_esquerdo_id=int(pneu_te_id),
            pneu_traseiro_direito_id=int(pneu_td_id),
            status='Ativo'
        )
        db.session.add(novo_set)

        # Atualizar status dos pneus
        for pid in pneus_ids:
            pneu = Pneu.query.get(int(pid))
            pneu.status = 'Montado'

        db.session.commit()
        flash(f'✅ Set {nome_set} montado com sucesso!', 'success')
        return redirect(url_for('sets'))

    # Listar sets ativos
    sets_ativos = SetPneus.query.filter_by(status='Ativo').all()
    sets_desmontados = SetPneus.query.filter_by(status='Desmontado').all()

    # Pneus disponíveis (apenas os que não estão montados)
    pneus_disponiveis = Pneu.query.filter_by(status='Disponível').all()
    carros = Carro.query.filter_by(status='Ativo').all()

    return render_template('sets.html', 
                         sets_ativos=sets_ativos,
                         sets_desmontados=sets_desmontados,
                         pneus_disponiveis=pneus_disponiveis,
                         carros=carros)

@app.route('/sets/<int:set_id>/desmontar', methods=['POST'])
def desmontar_set(set_id):
    if not is_logged_in():
        return redirect(url_for('login'))

    set_pneus = SetPneus.query.get_or_404(set_id)
    set_pneus.status = 'Desmontado'

    # Liberar pneus
    for pneu in [set_pneus.pneu_de, set_pneus.pneu_dd, set_pneus.pneu_te, set_pneus.pneu_td]:
        if pneu:
            pneu.status = 'Disponível'

    db.session.commit()
    flash(f'Set {set_pneus.nome} desmontado!', 'success')
    return redirect(url_for('sets'))

# ==================== ROTAS - VISUALIZAR DADOS ====================

@app.route('/pneus')
def visualizar_pneus():
    if not is_logged_in():
        return redirect(url_for('login'))

    # Filtros
    status_filtro = request.args.get('status')
    carro_filtro = request.args.get('carro')
    condicao_filtro = request.args.get('condicao')

    query = Pneu.query

    if status_filtro:
        query = query.filter_by(status=status_filtro)
    if carro_filtro:
        query = query.filter_by(carro_id=int(carro_filtro))
    if condicao_filtro:
        query = query.filter_by(condicao=condicao_filtro)

    pneus = query.order_by(Pneu.nome).all()

    # Opções de filtro
    status_disponiveis = db.session.query(Pneu.status).distinct().all()
    condicao_disponiveis = db.session.query(Pneu.condicao).distinct().all()
    carros = Carro.query.all()

    return render_template('visualizar_pneus.html',
                         pneus=pneus,
                         status_disponiveis=[s[0] for s in status_disponiveis],
                         condicao_disponiveis=[c[0] for c in condicao_disponiveis],
                         carros=carros)

@app.route('/pneus/<int:pneu_id>/historico')
def historico_pneu(pneu_id):
    if not is_logged_in():
        return redirect(url_for('login'))

    pneu = Pneu.query.get_or_404(pneu_id)
    medicoes = Medicao.query.filter_by(pneu_id=pneu_id).order_by(Medicao.data_medicao).all()

    return render_template('historico_pneu.html', pneu=pneu, medicoes=medicoes)

@app.route('/pneus/<int:pneu_id>/descartar', methods=['POST'])
def descartar_pneu(pneu_id):
    if not is_logged_in():
        return redirect(url_for('login'))

    pneu = Pneu.query.get_or_404(pneu_id)
    pneu.status = 'Descartado'

    db.session.commit()
    flash(f'Pneu {pneu.nome} descartado!', 'warning')
    return redirect(url_for('visualizar_pneus'))


@app.route('/pneus/<int:pneu_id>/graficos')
def graficos_pneu(pneu_id):
    """Página de análise gráfica do desgaste do pneu"""
    if not is_logged_in():
        return redirect(url_for('login'))

    pneu = Pneu.query.get_or_404(pneu_id)
    medicoes = Medicao.query.filter_by(pneu_id=pneu_id).order_by(Medicao.data_medicao).all()

    # Preparar dados para JavaScript (formato JSON)
    medicoes_json = []
    for medicao in medicoes:
        medicoes_json.append({
            'data': medicao.data_medicao.strftime('%d/%m/%Y'),
            'interno': float(medicao.interno),
            'centro_interno': float(medicao.centro_interno),
            'centro_externo': float(medicao.centro_externo),
            'externo': float(medicao.externo),
            'profundidade_media': float(medicao.profundidade_media),
            'km_total': float(medicao.km_total),
            'voltas': medicao.voltas
        })

    return render_template('graficos_pneu.html', 
                         pneu=pneu, 
                         medicoes=medicoes,
                         medicoes_json=json.dumps(medicoes_json))

# ==================== INICIALIZAÇÃO DO BANCO ====================

def init_db():
    with app.app_context():
        db.create_all()

        # Criar usuário padrão se não existir
        if not User.query.first():
            admin = User(
                username='admin',
                email='admin@tiremanagement.com',
                password_hash=generate_password_hash('admin123')
            )
            db.session.add(admin)

        # Criar carros padrão
        if not Carro.query.first():
            carros_default = [
                Carro(nome='Carro A', numero='11', piloto='Piloto 1', categoria='Stock Car', status='Ativo'),
                Carro(nome='Carro B', numero='22', piloto='Piloto 2', categoria='Stock Car', status='Ativo'),
                Carro(nome='Carro C', numero='33', piloto='Piloto 3', categoria='Stock Car', status='Ativo')
            ]
            for carro in carros_default:
                db.session.add(carro)

        # Criar pistas padrão
        if not Pista.query.first():
            pistas_default = [
                Pista(nome='Circuito dos Cristais', km_por_volta=3.477, localizacao='Curvelo-MG'),
                Pista(nome='Autódromo Zilmar Beux', km_por_volta=3.115, localizacao='Cascavel-PR'),
                Pista(nome='Interlagos', km_por_volta=4.309, localizacao='São Paulo-SP'),
                Pista(nome='Autódromo Ayrton Senna', km_por_volta=3.835, localizacao='Goiânia-GO'),
                Pista(nome='Autódromo de Cuiabá', km_por_volta=3.408, localizacao='Cuiabá-MT'),
                Pista(nome='Velocitta', km_por_volta=3.493, localizacao='Mogi Guaçu-SP'),
                Pista(nome='Autódromo de Chapecó', km_por_volta=3.762, localizacao='Chapecó-SC'),
                Pista(nome='Autódromo Nelson Piquet', km_por_volta=5.476, localizacao='Brasília-DF'),
                Pista(nome='Velopark', km_por_volta=3.013, localizacao='Nova Santa Rita-RS')
            ]
            for pista in pistas_default:
                db.session.add(pista)

        db.session.commit()
        print('Banco de dados inicializado com sucesso!')

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
