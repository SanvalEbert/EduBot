/*
MELHORIA — Limite de erro (Error Boundary).

Sem isto, qualquer exceção em um componente derrubava a tela inteira para um
branco silencioso. Agora um erro de render é capturado e mostra uma tela de
recuperação com botão de recarregar, em vez de quebrar todo o app.
*/
import { AlertTriangle } from "lucide-react";
import { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Erro não tratado na interface:", error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 p-6 text-center">
        <AlertTriangle className="text-rose-500" size={48} />
        <h1 className="text-2xl font-bold text-ink">Algo deu errado na interface</h1>
        <p className="max-w-md text-muted">
          Ocorreu um erro inesperado ao exibir esta tela. Recarregue a página para tentar novamente.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="h-11 rounded-[8px] bg-brand px-6 font-semibold text-white"
        >
          Recarregar
        </button>
      </div>
    );
  }
}
