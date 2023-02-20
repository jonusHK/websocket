let reconnectTimeout = null;
let selfClosing = false;

function startAttemptingToEstablishConnection() {
  reconnectTimeout = setTimeout(() => establishWebSocketConnection(), 5000);
}

function establishWebSocketConnection() {
    const label = document.getElementById("status-label");
    const userProfileId = 1;
    const socket = new WebSocket(`ws://localhost:8000/api/v1/chats/rooms/${userProfileId}`);
    // 연결 성공
    socket.onopen = function (event) {
        label.innerHTML = "연결 성공";

         if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
         }
    }

    // 서버가 데이터 송신 시, OnMessage 이벤트 발생
    socket.onmessage = function (event) {
        try {
            const json = JSON.parse(event.data)
            console.log('json - ', json);
        } catch (e) {
            console.log('Received wrong data.')
        }
    }

    // 연결 종료
    socket.onclose = function (event) {
        // 비정상적 연결 종료 시, 일정 시간 이후 웹소켓 재연결 시도
        if (selfClosing === false) {
            startAttemptingToEstablishConnection();
            return;
        }

        const code = event.code;
        const reason = event.reason;
        const wasClean = event.wasClean;

        if (wasClean) {
            label.innerHTML = "연결 종료";
        } else {
            label.innerHTML = "연결 종료 " + reason + "(Code: " + code + ")";
        }
    }

    // 예기치 못한 동작이나 오류 발생
    socket.onerror = function (event) {
        label.innerHTML = "에러 발생 - " + event;
    }
}

window.onload = function() {
    establishWebSocketConnection();
}
