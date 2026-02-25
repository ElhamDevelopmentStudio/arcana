import { useUiStore } from "@/app/store/uiStore";

import Button from "@/shared/ui/Button";

function ToastStack() {
  const messages = useUiStore((state) => state.messages);
  const removeMessage = useUiStore((state) => state.removeMessage);

  if (messages.length === 0) {
    return null;
  }

  return (
    <aside className="toast-stack" aria-live="polite">
      {messages.map((message) => (
        <article key={message.id} className={`toast toast--${message.kind}`}>
          <div>
            <h3>{message.title}</h3>
            {message.detail ? <p>{message.detail}</p> : null}
          </div>
          <Button variant="ghost" onClick={() => removeMessage(message.id)}>
            Dismiss
          </Button>
        </article>
      ))}
    </aside>
  );
}

export default ToastStack;
