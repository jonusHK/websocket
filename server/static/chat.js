// 웹소켓 지원 브라우저 여부 확인
// if (window.WebSocket) {
//     console.log("WebSockets supported.");
// } else {
//    console.log("WebSockets not supported.");
// }

window.onload = function() {
    const textView = document.getElementById("text-view");
    const buttonSend = document.getElementById("send-button");
    const buttonStop = document.getElementById("stop-button");
    const label = document.getElementById("status-label");

    const socket = new WebSocket("ws://localhost:8000/chat");

    // 연결이 성공적으로 이뤄진 후 발생
    socket.onopen = function (event) {
        label.innerHTML = "연결 성공";
    }

    // 서버가 데이터를 보낼 때마다 OnMessage 이벤트 발생
    socket.onmessage = function (event) {
        if (typeof event.data == "string") {
            label.innerHTML = label.innerHTML + "<br />" + event.data;
        }
    }

    // 대화 종료 (event 의 code, reason, wasClean 파라미터로 종료된 이류 확인 가능)
    socket.onclose = function (event) {
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
        // 연결이 열려 있으면 데이터 전송
        if (socket.readyState === WebSocket.OPEN) {
            socket.send(textView.value);
        }
    }

    buttonStop.onclick = function () {
        // 연결이 열려 있는 경우 종료
        if (socket.readyState === WebSocket.OPEN) {
            socket.close();
        }
    }
}
