import streamlit as st
import random

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Jogo da Velha - IA", page_icon="🎮", layout="centered")

# --- LÓGICA DA IA (MINIMAX) ---
def verificar_vitoria(tabuleiro, jogador):
   for i in range(3):
      if all(tabuleiro[i][j] == jogador for j in range(3)) or all(tabuleiro[j][i] == jogador for j in range(3)):
         return True
   if (tabuleiro[0][0] == tabuleiro[1][1] == tabuleiro[2][2] == jogador) or \
           (tabuleiro[0][2] == tabuleiro[1][1] == tabuleiro[2][0] == jogador):
      return True
   return False


def tabuleiro_cheio(tabuleiro):
   return all(celula != " " for linha in tabuleiro for celula in linha)


def obter_posicoes_livres(tabuleiro):
   return [(r, c) for r in range(3) for c in range(3) if tabuleiro[r][c] == " "]


def minimax(tabuleiro, profundidade, maximizando):
   if verificar_vitoria(tabuleiro, "O"): return 1
   if verificar_vitoria(tabuleiro, "X"): return -1
   if tabuleiro_cheio(tabuleiro): return 0

   if maximizando:
      melhor_pontuacao = float('-inf')
      for r, c in obter_posicoes_livres(tabuleiro):
         tabuleiro[r][c] = "O"
         pontuacao = minimax(tabuleiro, profundidade + 1, False)
         tabuleiro[r][c] = " "
         melhor_pontuacao = max(pontuacao, melhor_pontuacao)
      return melhor_pontuacao
   else:
      melhor_pontuacao = float('inf')
      for r, c in obter_posicoes_livres(tabuleiro):
         tabuleiro[r][c] = "X"
         pontuacao = minimax(tabuleiro, profundidade + 1, True)
         tabuleiro[r][c] = " "
         melhor_pontuacao = min(pontuacao, melhor_pontuacao)
      return melhor_pontuacao


def jogada_ia_inteligente(tabuleiro):
   melhor_pontuacao = float('-inf')
   melhor_jogada = None
   for r, c in obter_posicoes_livres(tabuleiro):
      tabuleiro[r][c] = "O"
      pontuacao = minimax(tabuleiro, 0, False)
      tabuleiro[r][c] = " "
      if pontuacao > melhor_pontuacao:
         melhor_pontuacao = pontuacao
         melhor_jogada = (r, c)
   return melhor_jogada


# --- INICIALIZAÇÃO DO ESTADO DA SESSÃO (SESSION STATE) ---
if "tabuleiro" not in st.session_state:
   st.session_state.tabuleiro = [[" " for _ in range(3)] for _ in range(3)]
if "game_over" not in st.session_state:
   st.session_state.game_over = False
if "mensagem" not in st.session_state:
   st.session_state.mensagem = ""


# --- FUNÇÃO DE REINICIAR ---
def reiniciar_jogo():
   st.session_state.tabuleiro = [[" " for _ in range(3)] for _ in range(3)]
   st.session_state.game_over = False
   st.session_state.mensagem = ""


# --- INTERFACE VISUAL DO STREAMLIT ---
st.title("🎮 Jogo da Velha com IA")
st.write("Desafie a Inteligência Artificial diretamente no seu navegador!")

# Seleção de Dificuldade lateral
dificuldade = st.sidebar.radio("Dificuldade da IA:", ("Fácil", "Impossível"), index=1)


# Função executada ao clicar em um botão do tabuleiro
def clique_botao(r, c):
   if st.session_state.tabuleiro[r][c] == " " and not st.session_state.game_over:
      # Turno do Humano (X)
      st.session_state.tabuleiro[r][c] = "X"

      if verificar_vitoria(st.session_state.tabuleiro, "X"):
         st.session_state.mensagem = "🎉 Parabéns! Você venceu a IA!"
         st.session_state.game_over = True
         return

      if tabuleiro_cheio(st.session_state.tabuleiro):
         st.session_state.mensagem = "🤝 O jogo terminou em empate!"
         st.session_state.game_over = True
         return

      # Turno da IA (O)
      posicoes_livres = obter_posicoes_livres(st.session_state.tabuleiro)
      if posicoes_livres:
         if dificuldade == "Fácil":
            ia_r, ia_c = random.choice(posicoes_livres)
         else:
            ia_r, ia_c = jogada_ia_inteligente(st.session_state.tabuleiro)

         st.session_state.tabuleiro[ia_r][ia_c] = "O"

         if verificar_vitoria(st.session_state.tabuleiro, "O"):
            st.session_state.mensagem = "🤖 Que pena! O computador venceu!"
            st.session_state.game_over = True


# Construção visual do Tabuleiro 3x3 usando colunas do Streamlit
for r in range(3):
   cols = st.columns(3)
   for c in range(3):
      conteudo = st.session_state.tabuleiro[r][c]
      # Define um rótulo invisível ou visível para o botão
      label = conteudo if conteudo != " " else " "

      # Estilização desabilitada se o jogo acabou ou a casa já foi preenchida
      desabilitado = st.session_state.game_over or conteudo != " "

      with cols[c]:
         st.button(
            label,
            key=f"btn_{r}_{c}",
            on_click=clique_botao,
            args=(r, c),
            disabled=desabilitado,
            use_container_width=True
         )

# Exibe o resultado final se houver
if st.session_state.mensagem:
   if "🎉" in st.session_state.mensagem:
      st.success(st.session_state.mensagem)
   elif "🤖" in st.session_state.mensagem:
      st.error(st.session_state.mensagem)
   else:
      st.info(st.session_state.mensagem)

# Botão de reiniciar destacado na tela
st.button("🔄 Reiniciar Partida", on_click=reiniciar_jogo, type="primary")