async function fetchData() {
    const res = await fetch('/data');
    const data = await res.json();
    document.getElementById('output').innerText = JSON.stringify(data, null, 2);
  }
  
  setInterval(fetchData, 1000);
  