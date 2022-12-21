import { helpers } from 'balm-ui'; // Default Usage

export default {
  required: {
    validate(value) {
      return !helpers.isEmpty(value);
    },
    message: '%s 필수 입력 항목입니다.'
  },
  email: {
    validate(value) {
        return /^[0-9a-zA-Z]([-_.]?[0-9a-zA-Z])*@[0-9a-zA-Z]([-_.]?[0-9a-zA-Z])*.[a-zA-Z]{2,3}$/.test(value);
    },
    message: '이메일 주소가 올바른 형식이 아닙니다.'
  },
  name: {
    validate(value) {
        return /^[가-힣]+$/.test(value)
    },
    message: '이름이 올바른 형식이 아닙니다.'
  },
  mobile: {
    validate(value) {
      value = value.replace(/\D/g, '');
      return /^010\d{7,8}$/.test(value);
    },
    message: '휴대폰 번호가 올바른 형식이 아닙니다.'
  },
  password: {
    validate(value) {
      return /^[A-Za-z0-9`~!@#\$%\^&\*\(\)\{\}\[\]\-_=\+\\|;:'"<>,\./\?]{8,16}$/.test(value);
    },
    message: '비밀번호는 8-16자의 영문 대소문자, 숫자, 특수문자로 구성되어야 합니다.'
  }
};