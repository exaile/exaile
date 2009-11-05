function toggle(id){
	elem = document.getElementById(id)
	if(elem.style.display=='')
		elem.style.display = 'none';
	else
		elem.style.display = '';

	return false;
}

function toggleElem(elem){
	while(elem.style==undefined)
		elem = elem.nextSibling;
	if(elem.style.display=='')
		elem.style.display = 'none';
	else
		elem.style.display = '';

	return false;
}

function hideElem(elem){
	while(elem.style==undefined)
		elem = elem.nextSibling;
	if(elem.style.display=='')
		elem.style.display = 'none';

	return false;
}

function doToggleElem(elem){
	var id = elem.id
	elem = elem.nextSibling
	while(elem.style==undefined)
		elem = elem.nextSibling;
	if(elem.style.display==''){
		elem.style.display = 'none';
		writeCookie(id, 'hide');
	}
	else{
		elem.style.display = '';
		deleteCookie(id);
	}

	return false;
}

function makeTogglePanels(){
var panels = document.getElementsByClassName('panel');
	for(var e=0;e<panels.length;e++){
		panels[e].getElementsByClassName('panel-title')[0].onclick = new Function("doToggleElem(this);");
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

	return false;
}

function makeToggleCds(){
	var albums = document.getElementsByClassName('cd-tr');
	for(var e=0;e<albums.length;e++){
		albums[e].onclick = new Function("toggleCD(this);");
		toggleCD(albums[e])
	}

	return false;
}

window.onload = function() {
	makeTogglePanels();
	makeToggleCds();
	hidePanels();
	onPageRefresh('');
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

function hidePanels(){
	var panels = document.getElementsByClassName('panel-title');
	for(var e=0;e<panels.length;e++){
		if(readCookie(panels[e].id)!=null){
			hideElem(panels[e].nextSibling)
		}
	}
}

function writeCookie(name, value)
{
	var argv=writeCookie.arguments;
	var argc=writeCookie.arguments.length;
	var expires=(argc > 2) ? argv[2] : null;
	var path=(argc > 3) ? argv[3] : null;
	var domain=(argc > 4) ? argv[4] : null;
	var secure=(argc > 5) ? argv[5] : false;
	document.cookie=name+"="+escape(value)+
	((expires==null) ? "" : ("; expires="+expires.toGMTString()))+
	((path==null) ? "" : ("; path="+path))+
	((domain==null) ? "" : ("; domain="+domain))+
	((secure==true) ? "; secure" : "");
}

function getCookieVal(offset)
{
	var endstr=document.cookie.indexOf (";", offset);
	if (endstr==-1) endstr=document.cookie.length;
	return unescape(document.cookie.substring(offset, endstr));
}

function readCookie(name)
{
	var arg=name+"=";
	var alen=arg.length;
	var clen=document.cookie.length;
	var i=0;
	while (i<clen)
		{
		var j=i+alen;
		if (document.cookie.substring(i, j)==arg) return getCookieVal(j);
		i=document.cookie.indexOf(" ",i)+1;
		if (i==0) break;
		
		}
	return null;
}

function deleteCookie(name)
{
	date=new Date;
	date.setFullYear(date.getFullYear()-1);
	writeCookie(name,null,date);
}
