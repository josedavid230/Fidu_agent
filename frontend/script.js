document.addEventListener('DOMContentLoaded', () => {
    const chatToggleBtn = document.getElementById('chat-toggle-btn');
    const chatContainer = document.getElementById('chat-container');
    const closeChatBtn = document.getElementById('close-chat-btn');
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');

    const showWelcomeMessage = () => {
        const welcomeText = `¡Bienvenido! Soy FidupreviBOT. ¿Qué te interesa consultar hoy?\n\nPuedes preguntarme sobre:\n- Fondos de Inversión Colectiva\n- Portafolios y rendimientos\n- Proceso de vinculación\n- Información de contacto`;
        appendMessage(welcomeText, 'bot-message');
    };

    const openChat = () => {
        chatContainer.style.display = 'flex';
        chatToggleBtn.style.display = 'none';
        // Muestra el mensaje de bienvenida solo si el chat está vacío
        if (chatBox.children.length === 0) {
            showWelcomeMessage();
        }
    };

    const closeChat = () => {
        chatContainer.style.display = 'none';
        chatToggleBtn.style.display = 'flex';
    };

    chatToggleBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openChat();
    });

    closeChatBtn.addEventListener('click', closeChat);

    document.addEventListener('click', (e) => {
        if (!chatContainer.contains(e.target) && e.target !== chatToggleBtn) {
            closeChat();
        }
    });

    chatContainer.addEventListener('click', (e) => {
        e.stopPropagation();
    });

    // Auto-ajuste de la altura del textarea
    userInput.addEventListener('input', () => {
        userInput.style.height = 'auto';
        userInput.style.height = (userInput.scrollHeight) + 'px';
    });

    const sendMessage = async () => {
        const question = userInput.value.trim();
        if (question === '') return;

        appendMessage(question, 'user-message');
        userInput.value = '';
        userInput.style.height = 'auto'; // Restablece la altura

        // Muestra el indicador de "escribiendo"
        const typingIndicator = showTypingIndicator();

        try {
            const response = await fetch('http://127.0.0.1:8000/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ question: question }),
            });

            removeTypingIndicator(typingIndicator);

            if (!response.ok) {
                throw new Error('La respuesta de la red no fue correcta');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let botMessageElement = null;

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                
                if (!botMessageElement) {
                    botMessageElement = appendMessage('', 'bot-message');
                }
                
                botMessageElement.textContent += chunk;
                chatBox.scrollTop = chatBox.scrollHeight;
            }

        } catch (error) {
            console.error('Hubo un problema con la operación de fetch:', error);
            if (typingIndicator) removeTypingIndicator(typingIndicator);
            appendMessage('Lo siento, no pude conectar con el servidor.', 'bot-message');
        }
    };

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault(); // Evita el salto de línea por defecto
            sendMessage();
        }
    });

    function appendMessage(text, className) {
        const messageElement = document.createElement('div');
        messageElement.textContent = text;
        messageElement.className = className;
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
        return messageElement; // Devuelve el elemento para poder actualizarlo
    }

    function showTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator bot-message';
        indicator.innerHTML = '<span></span><span></span><span></span>';
        chatBox.appendChild(indicator);
        chatBox.scrollTop = chatBox.scrollHeight;
        return indicator;
    }

    function removeTypingIndicator(indicator) {
        if (indicator) {
            chatBox.removeChild(indicator);
        }
    }
});
