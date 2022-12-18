<script>
import HeaderLayer from './HeaderLayer.vue';
import SidebarLayer from './SidebarLayer.vue';

export default {
  name: 'App',
  data() {
    return {
    }
  },
  components: {
    HeaderLayer,
    SidebarLayer
  }
}
</script>

<template>
    <div style="height:100%; display:flex; flex-direction:row; justify-content:space-between;">
        <div style="width:5%; height:100%; display:flex; flex-direction:column; justify-content:space-between; background-color:lightgrey;">
            <sidebar-layer/>
        </div>
        <div style="width:95%; height:100%; display:flex; flex-direction:column;">
            <div style="width:100%; height:5%;">
                <header-layer/>
            </div>
        </div>
    </div>
</template>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  margin-top: 10px;
  width: 100vw;
  height: 100vh;
}
</style>
