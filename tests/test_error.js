try {
  atob("invalid chars!!");
} catch(e) {
  console.log(e.toString());
}
try {
  document.querySelector("123");
} catch(e) {
  console.log(e.toString());
}
