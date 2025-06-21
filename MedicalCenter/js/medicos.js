// Función para actualizar el reloj
function updateClock() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('es-MX', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    const dateString = now.toLocaleDateString('es-MX', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
    
    const clockElement = document.getElementById('live-clock');
    if(clockElement) {
        clockElement.innerHTML = `<i class="fas fa-clock me-1"></i>${dateString} - ${timeString}`;
    }
}

// Actualizar el reloj cada segundo
setInterval(updateClock, 1000);

// Inicializar el reloj al cargar la página
document.addEventListener('DOMContentLoaded', function() {
    updateClock();
    
    // Mostrar/ocultar selector de reemplazo al eliminar médico
    const reemplazarCheck = document.getElementById('reemplazarMedico');
    const selectReemplazo = document.getElementById('selectReemplazo');
    
    if(reemplazarCheck && selectReemplazo) {
        reemplazarCheck.addEventListener('change', function() {
            selectReemplazo.style.display = this.checked ? 'block' : 'none';
        });
    }
    
    // Aquí puedes agregar más funcionalidades específicas para el módulo de médicos
    console.log('Módulo de médicos cargado');
});