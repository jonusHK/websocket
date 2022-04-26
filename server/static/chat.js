// 웹소켓 지원 브라우저 여부 확인
// if (window.WebSocket) {
//     console.log("WebSockets supported.");
// } else {
//    console.log("WebSockets not supported.");
// }

const socket = new WebSocket("ws://echo.websocket.org");

// 연결이 성공적으로 이뤄진 후 발생
socket.onopen = function(event) {
    console.log("Connection established.");

    // 모든 자원을 초기화하고 사용자에게 메시지를 보여주는 코드
    const label = document.getElementById("status-label");
    label.innerHTML = "Connection established!";
}

// 서버가 데이터를 보낼 때마다 OnMessage 이벤트 발생
socket.onmessage = function(event) {
    if (typeof event.data == "string") {
        // 서버가 텍스트 데이터 전송한 경우
        const label = document.getElementById("status-label");
        label.innerHTML = label.innerHTML + "<br />" + event.data;
    }
}

// 대화 종료 (event 의 code, reason, wasClean 파라미터로 종료된 이류 확인 가능)
socket.onclose = function(event) {
    console.log("Connection closed.");

    const code = event.code;
    const reason = event.reason;
    const wasClean = event.wasClean;

    const label = document.getElementById("status-label");

    if (wasClean) {
        label.innerHTML = "Connection closed normally.";
    } else {
        label.innerHTML = "Connection closed with message " + reason + "(Code: " + code + ")";
    }
}

// 예기치 못한 동작이나 오류 발생
socket.onerror = function(event) {
    console.log("Error occurred.");

    const label = document.getElementById("status-label");
    label.innerHTML = "Error: " + event;
}

const textView = document.getElementById("text-view");
const buttonSend = document.getElementById("send-button");
const buttonStop = document.getElementById("stop-button");

buttonSend.onclick = function() {
    // 연결이 열려 있으면 데이터 전송
    if (socket.readyState === WebSocket.OPEN) {
        socket.send(textView.value);
    }
}

buttonStop.onclick = function() {
    // 연결이 열려 있는 경우 종료
    if (Socket.readyState === WebSocket.OPEN) {
        socket.close();
    }
}