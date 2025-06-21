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
    
    document.getElementById('live-clock').innerHTML = 
        `<i class="fas fa-clock me-1"></i>${dateString} - ${timeString}`;
}

// Actualizar el reloj cada segundo
setInterval(updateClock, 1000);

// Inicializar el reloj al cargar la página
document.addEventListener('DOMContentLoaded', updateClock);

// Funcionalidad para el modal de cancelar cita
document.addEventListener('DOMContentLoaded', function() {
    const btnSeleccionarCancelar = document.getElementById('btnSeleccionarCancelar');
    const confirmacionCancelacion = document.getElementById('confirmacionCancelacion');
    
    if(btnSeleccionarCancelar) {
        btnSeleccionarCancelar.addEventListener('click', function() {
            // Ocultar botón de selección y mostrar confirmación
            this.style.display = 'none';
            confirmacionCancelacion.style.display = 'block';
        });
    }
    
    // Configurar los botones de editar cita
    document.querySelectorAll('.btn-editar-cita').forEach(btn => {
        btn.addEventListener('click', function() {
            const citaId = this.getAttribute('data-cita-id');
            // Aquí iría la lógica para cargar los datos de la cita
            console.log('Editando cita ID:', citaId);
        });
    });
});