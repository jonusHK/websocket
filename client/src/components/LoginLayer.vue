<script>
export default {
    data() {
        return {
        userEmail: null,
        userPassword: null,
        };
    },
    methods: {

        // try {
        //   this.$axios
        //     .post(HOST + "/signin", JSON.stringify(saveData), {
        //       headers: {
        //         "Content-Type": `application/json`,
        //       },
        //     })
        //     .then((res) => {
        //       if (res.status === 200) {
        //         // 로그인 성공시 처리해줘야할 부분
        //       }
        //     });
        // } catch (error) {
        //   console.error(error);
        // }
    },
}
</script>

<template>
    <div>로그인</div>
  </template>
