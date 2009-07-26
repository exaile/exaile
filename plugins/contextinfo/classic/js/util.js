function toggle(id){
	elem = document.getElementById(id)
	if(elem.style.display=='')
		elem.style.display = 'none';
	else
		elem.style.display = '';
}

function toggleElem(elem){
while(elem.style==undefined)
	elem = elem.nextSibling;
if(elem.style.display=='')
	elem.style.display = 'none';
else
	elem.style.display = '';
}

function makeTogglePanels(){
var panels = document.getElementsByClassName('panel');
	for(var e=0;e<panels.length;e++){
		panels[e].getElementsByClassName('panel-title')[0].onclick = new Function("toggleElem(this.nextSibling);");
	}
}

function toggleCD(elem){
	do{
		elem = elem.nextSibling;
		while(elem.style==undefined)
			elem = elem.nextSibling
		if(elem.style.display=='')
			elem.style.display = 'none';
		else
			elem.style.display = '';
	}
	while(elem.nextSibling)
}

function makeToggleCds(){
	var albums = document.getElementsByClassName('cd-tr');
	for(var e=0;e<albums.length;e++){
		albums[e].onclick = new Function("toggleCD(this);");
		toggleCD(albums[e])
	}
}

window.onload = function() {
	makeTogglePanels();
	makeToggleCds()
	onPageRefresh('')
}

function onPageRefresh(id){
	var panels = document.getElementsByClassName('panel');
	for(var e=0;e<panels.length;e++){
		if(panels[e].getElementsByClassName('panel-content')[0].childNodes[0].innerHTML == ''){
			panels[e].style.display = 'none';
		}
		else{
			panels[e].style.display = '';
		}
	}
	if(id!=''){
		albums = document.getElementById(id).getElementsByClassName('cd-tr');
		for(var e=0;e<albums.length;e++){
			albums[e].onclick = new Function("toggleCD(this);");
			toggleCD(albums[e])
		}
	}
}
