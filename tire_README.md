# 🏁 Tire Management System - Stock Car Pro Series 2026

Sistema completo de gestão de pneus para equipes de automobilismo, desenvolvido com Flask e SQLAlchemy.

## 📋 Funcionalidades

### Gerenciamento de Etapas
- ✅ Calendário completo Stock Car 2026 (12 etapas)
- ✅ Controle de etapa atual
- ✅ Sistema de avanço de etapas com seleção de 4 pneus
- ✅ Histórico completo de etapas concluídas

### Gestão de Pneus
- ✅ Compra de pneus com limite por etapa (16 na 1ª etapa, 8 nas seguintes)
- ✅ Cadastro automático com código de barras único
- ✅ Controle de quilometragem e profundidade
- ✅ Status por etapa (Disponível, Em uso, Montado, Descartado)
- ✅ Visualização e filtros avançados

### Medições e Monitoramento
- ✅ Registro de medições por evento (Treino, Classificação, Corrida)
- ✅ Cálculo automático de quilometragem baseado em voltas
- ✅ Medição de profundidade em 4 pontos
- ✅ Sistema de alertas (ok, alerta, crítico)
- ✅ Histórico completo por pneu com gráficos

### Montagem de Sets
- ✅ Criação de sets de 4 pneus (DE, DD, TE, TD)
- ✅ Controle de pneus montados por etapa
- ✅ Desmontagem de sets com liberação dos pneus

### Cadastros Auxiliares
- ✅ Gerenciamento de carros (nome, número, piloto)
- ✅ Gerenciamento de pistas (nome, km/volta, localização)
- ✅ Usuários com autenticação segura

## 🚀 Como Usar

### 1. Instalação

```bash
# Clone ou copie os arquivos do projeto
cd tire-management

# Crie um ambiente virtual (recomendado)
python -m venv venv

# Ative o ambiente virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instale as dependências
pip install flask flask-sqlalchemy werkzeug python-dotenv reportlab
```

### 2. Configuração

Edite o arquivo `.env` com suas configurações:

```env
SECRET_KEY=sua-chave-secreta-aqui
FLASK_ENV=development
FLASK_DEBUG=True
```

### 3. Inicialização

```bash
# Execute o aplicativo
python app.py
```

Na primeira execução, o sistema irá:
- Criar o banco de dados SQLite
- Cadastrar usuário padrão (admin/admin123)
- Cadastrar 3 carros padrão
- Cadastrar 9 pistas da Stock Car
- Criar calendário 2026 completo

### 4. Acesso

Abra seu navegador em: **http://localhost:5000**

**Credenciais padrão:**
- Usuário: `admin`
- Senha: `admin123`

## 📊 Estrutura do Sistema

### Modelos de Dados

- **User**: Usuários do sistema
- **Carro**: Carros da equipe
- **Pista**: Pistas cadastradas
- **Etapa**: Calendário de etapas
- **Pneu**: Cadastro de pneus
- **Medicao**: Histórico de medições
- **SetPneus**: Sets montados (4 pneus)
- **HistoricoEtapa**: Histórico de etapas concluídas
- **ConfiguracaoSistema**: Controle da etapa atual

### Rotas Principais

| Rota | Descrição |
|------|-----------|
| `/` | Dashboard com estatísticas |
| `/login` | Página de login |
| `/etapas` | Gerenciar etapas e calendário |
| `/pneus/comprar` | Comprar novos pneus |
| `/medicoes` | Registrar medições |
| `/sets` | Montar/desmontar sets |
| `/carros` | Gerenciar carros |
| `/pistas` | Gerenciar pistas |
| `/pneus` | Visualizar pneus com filtros |

## 📁 Estrutura de Arquivos

```
tire-management/
├── app.py                      # Aplicação Flask principal
├── .env                        # Configurações (não commitar!)
├── tire_management.db          # Banco SQLite (criado automaticamente)
├── README.md                   # Este arquivo
├── templates/                  # Templates HTML
│   ├── base.html              # Layout base
│   ├── login.html             # Página de login
│   ├── index.html             # Dashboard
│   ├── comprar_pneus.html     # Compra de pneus
│   ├── etapas.html            # Gerenciar etapas
│   ├── medicoes.html          # Registrar medições
│   ├── sets.html              # Montagem de sets
│   ├── carros.html            # Gerenciar carros
│   ├── pistas.html            # Gerenciar pistas
│   ├── visualizar_pneus.html  # Lista de pneus
│   └── historico_pneu.html    # Histórico individual
└── static/                     # Arquivos estáticos (CSS, JS, imagens)
```

## 🏆 Regras de Negócio

### Compra de Pneus
- **Etapa 1**: Até 16 pneus novos
- **Demais etapas**: Até 8 pneus novos por etapa
- Pneus da etapa anterior continuam disponíveis

### Avanço de Etapa
- Selecionar exatamente 4 pneus para próxima etapa
- Pneus não selecionados são descartados
- Sistema cria registro no histórico

### Status dos Pneus
- **Novo**: Pneu sem uso
- **Usado**: Pneu com ao menos 1 medição

### Status na Etapa
- **Disponível**: Pode ser usado ou montado em set
- **Em uso**: Tem medições recentes
- **Montado**: Parte de um set ativo
- **Descartado**: Não selecionado para próxima etapa

### Condições de Alerta
**Por Quilometragem:**
- OK: < 80% do limite
- Alerta: 80-100% do limite
- Crítico: > 100% do limite

**Por Profundidade (TWI):**
- OK: > 2.0 mm
- Alerta: 1.5-2.0 mm
- Crítico: < 1.5 mm

## 🛠️ Tecnologias Utilizadas

- **Flask 3.0** - Framework web
- **SQLAlchemy** - ORM para banco de dados
- **SQLite** - Banco de dados
- **Bootstrap 5.3** - Framework CSS
- **Bootstrap Icons** - Ícones
- **ReportLab** - Geração de PDFs (futuro)
- **Werkzeug** - Segurança e hashing de senhas

## 📝 Notas de Desenvolvimento

### Próximas Melhorias
- [ ] Gráficos interativos (Plotly/Chart.js)
- [ ] Exportação para Excel
- [ ] Relatórios em PDF
- [ ] Sistema de notificações
- [ ] API REST
- [ ] Modo escuro
- [ ] Múltiplos usuários com permissões

### Baseado em
Sistema original desenvolvido em Streamlit, convertido para Flask mantendo todas as funcionalidades e melhorando a experiência de usuário com interface profissional.

## 📄 Licença

Sistema desenvolvido para uso em equipes de Stock Car Pro Series 2026.

## 👥 Suporte

Para dúvidas ou sugestões, entre em contato com a equipe de desenvolvimento.

---

**Desenvolvido com ❤️ para Stock Car Pro Series 2026** 🏁
