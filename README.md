# 📊 DataLens

**Dashboard inteligente que analisa qualquer CSV automaticamente — estatísticas, gráficos e um resumo em linguagem natural, gerados sem nenhuma configuração manual.**

Você envia um arquivo `.csv`. O DataLens lê os dados, identifica o tipo de cada coluna, calcula estatísticas, detecta problemas de qualidade, escolhe os gráficos certos para o seu dataset e escreve um resumo executivo — tudo automaticamente, em segundos.

---

## ✨ Funcionalidades

- **Upload simples** — arraste um CSV ou selecione pelo navegador
- **Detecção automática de tipos de coluna** — numérica, categórica, data ou booleana, mesmo quando a coluna de data chega como texto no CSV
- **Estatísticas automáticas** — média, mediana, moda, mínimo, máximo, desvio padrão e quartis para cada coluna numérica
- **KPIs em cards** — total de registros, colunas, valores ausentes, duplicados, colunas numéricas e categóricas
- **Qualidade dos dados** — detecção de valores nulos, linhas duplicadas, colunas constantes, outliers (via IQR) e datas inválidas
- **Gráficos escolhidos automaticamente** — o sistema decide o que faz sentido gerar (barras, pizza, histograma, linha do tempo, scatter, heatmap de correlação) com base no tipo de cada coluna, sem exigir nenhuma configuração
- **Resumo com IA** — um resumo executivo em português, gerado pela API da Anthropic (Claude), com fallback local baseado em regras caso a API não esteja configurada ou disponível
- **Interface dark, responsiva, com identidade visual própria** — tema escuro pensado para transmitir a aparência de um produto SaaS real

---

## 🛠️ Tecnologias

| Camada | Tecnologias |
|---|---|
| Front-end | HTML5, CSS3, JavaScript (vanilla) |
| Back-end | Python, Flask |
| Manipulação de dados | Pandas, NumPy |
| Visualização | Plotly |
| Inteligência Artificial | API da Anthropic (Claude) |

---

## 📁 Estrutura do projeto

```
datalens/
│
├── app.py                 # Rotas Flask — orquestra todo o pipeline
├── requirements.txt
│
├── static/
│   ├── css/style.css       # Tema escuro, animações, responsividade
│   └── js/main.js          # Upload, chamada à API, renderização do dashboard
│
├── templates/
│   └── index.html
│
├── uploads/                # Pasta temporária — arquivos são apagados após a análise
│
├── utils/
│   ├── analyzer.py         # Leitura do CSV, classificação de colunas, estatísticas, qualidade dos dados
│   ├── charts.py           # Seleção e geração automática dos gráficos (Plotly)
│   ├── insights.py         # Geração do resumo em linguagem natural (IA + fallback local)
│   └── validators.py       # Validação do arquivo enviado
│
└── README.md
```

---

## 🚀 Como rodar localmente

### Pré-requisitos

- Python 3.10 ou superior
- pip

### 1. Clone o repositório

```bash
git clone https://github.com/Cardoso55/datalens.git
cd datalens
```

### 2. Crie um ambiente virtual (recomendado)

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. (Opcional) Configure a chave da API de IA

Sem essa etapa o projeto funciona normalmente — o resumo é gerado localmente por um modo fallback baseado em regras.

```bash
export ANTHROPIC_API_KEY="sua_chave_aqui"     # Windows: set ANTHROPIC_API_KEY=sua_chave_aqui
```

### 5. Rode a aplicação

```bash
python app.py
```

Acesse **http://127.0.0.1:5000** no navegador, envie um arquivo `.csv` e veja o dashboard ser montado automaticamente.

---

## 🧠 Como funciona (visão geral da arquitetura)

```
Upload do CSV
      │
      ▼
validators.py    → valida extensão, tamanho e integridade do arquivo
      │
      ▼
analyzer.py       → lê o CSV com Pandas, classifica colunas, calcula
      │              estatísticas, KPIs e o relatório de qualidade
      ▼
charts.py         → decide quais gráficos fazem sentido para esse
      │              dataset e gera cada um em Plotly
      ▼
insights.py        → envia o resumo estatístico (nunca o CSV bruto)
      │              para a IA, que devolve um resumo em português
      ▼
app.py            → junta tudo em um único JSON e devolve para o front-end
      │
      ▼
main.js            → renderiza KPIs, qualidade dos dados, gráficos e
                      a pré-visualização, tudo a partir dessa resposta
```

Algumas decisões de design vale destacar:

- **A IA nunca recebe o dataset bruto** — só o resumo estatístico já calculado pelo `analyzer.py`. Isso é mais rápido, mais barato e evita expor dados desnecessariamente.
- **O resumo de IA tem fallback local** — se a chave da API não estiver configurada, ou a chamada falhar por qualquer motivo, o `insights.py` gera um resumo coerente localmente, baseado em regras. O dashboard nunca fica quebrado.
- **Nenhum arquivo fica salvo** — o CSV enviado é apagado do servidor logo depois da análise (`app.py`, bloco `finally` da rota `/analyze`).
- **Seleção de gráficos é adaptativa, não fixa** — colunas que se comportam como identificador (ex.: um ID de pedido, onde quase todo valor é único) são ignoradas na geração de gráficos, porque um gráfico de barras nesse caso não comunica nada.

---

## 🧪 Testando os módulos isoladamente

Cada módulo em `utils/` tem um teste manual embutido, útil para depurar sem precisar subir o Flask:

```bash
cd utils
python analyzer.py     # imprime o JSON completo da análise de um CSV de exemplo
python charts.py       # imprime a lista de gráficos gerados
python insights.py     # imprime o resumo em modo fallback
```

---

## 🚀 Possíveis melhorias futuras

- [ ] Upload de arquivos Excel (`.xlsx`)
- [ ] Comparação entre múltiplos datasets
- [ ] Exportação de relatórios em PDF
- [ ] Histórico de análises
- [ ] Login de usuários e salvamento de dashboards
- [ ] Sugestões automáticas de limpeza dos dados
- [ ] Recomendações de modelos de Machine Learning com base no dataset
- [ ] Chat com IA para consultar o dataset em linguagem natural

---

## 👤 Autor

Desenvolvido por **Gabriel Cardoso da Silva** como projeto de portfólio.

[LinkedIn](https://linkedin.com/in/cardoso-gabriel0308) · [GitHub](https://github.com/Cardoso55)

---

## 📄 Licença

Este projeto está sob a licença MIT — sinta-se à vontade para usar, estudar e adaptar.