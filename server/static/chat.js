// 웹소켓 지원 브라우저 여부 확인
// if (window.WebSocket) {
//     console.log("WebSockets supported.");
// } else {
//    console.log("WebSockets not supported.");
// }

let reconnectTimeout = null;
let selfClosing = false;

function uuidv4() {
  return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
    (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
  );
}

function startAttemptingToEstablishConnection() {
  reconnectTimeout = setTimeout(() => establishWebSocketConnection(), 5000);
}

function establishWebSocketConnection() {
    const textView = document.getElementById("text-view");
    const buttonSend = document.getElementById("send-button");
    const buttonStop = document.getElementById("stop-button");
    const label = document.getElementById("status-label");
    const roomId = 'room_1';
    const clientId = uuidv4();
    const socket = new WebSocket(`ws://localhost:8000/chat/${roomId}/${clientId}`);

    // 연결 성공
    socket.onopen = function (event) {
        label.innerHTML = "연결 성공";

         if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
         }
    }

    // 서버가 데이터 송신 시, OnMessage 이벤트 발생
    socket.onmessage = function (event) {
        if (typeof event.data == "string") {
            label.innerHTML = label.innerHTML + "<br />" + event.data;
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

    buttonSend.onclick = function () {
        if (socket.readyState === WebSocket.OPEN) {
            socket.send(textView.value);
        }
    }

    buttonStop.onclick = function () {
        if (socket.readyState === WebSocket.OPEN) {
            selfClosing = true;
            socket.close(4000, 'self closing');
        }
    }
}

window.onload = function() {
    establishWebSocketConnection();
}
