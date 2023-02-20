<script>
import { reactive, toRef } from 'vue';
import _ from 'lodash';

export default {
    name: 'FollowingListLayer',
    props: {
        followings: Array,
    },
    setup (props, { emit }) {
      const state = reactive({
        followings: toRef(props, 'followings'),
      });
      const getDefaultProfileImage = function(obj) {
        if (obj.files.length > 0) {
            for (const i in obj.files) {
                const file = obj.files[i];
                if (file.use_type === 'user_profile_image' && file.is_default === true) {
                    return file.url;
                }
            }
            return null;
        }
        return null;
      }
      const onClickProfile = function(userProfile) {
        emit('followingInfo', userProfile.id);
      }
      return {
        state,
        getDefaultProfileImage,
        onClickProfile,
      }
    }
}
</script>

<template>
    <div class="chat-body-list" v-if="state.followings">
        <div v-for="obj in state.followings" :key="obj.id" class="following-list" @click="onClickProfile(obj)">
            <div v-if="getDefaultProfileImage(obj) !== null" class="following-profile" :style="{
                backgroundImage: 'url(' + getDefaultProfileImage(obj) + ')',
                backgroundRepeat: 'no-repeat',
                backgroundSize: 'cover',
                backgroundPosition: 'center center',
            }"></div>
            <div v-else class="following-profile-default">
                <p><ui-icon style="width: 100%; height: 100%; color: #b3e5fc">person</ui-icon></p>
            </div>
            <p>{{ obj.nickname }}</p>
        </div>
    </div>
</template>

<style scoped>
</style>