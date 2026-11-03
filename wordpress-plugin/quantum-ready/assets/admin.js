/* Quantum Ready: copy buttons for the ready-made host request. */
( function () {
	document.querySelectorAll( '.qr-copy' ).forEach( function ( button ) {
		button.addEventListener( 'click', function () {
			var field = document.getElementById( button.getAttribute( 'data-target' ) );
			if ( ! field ) {
				return;
			}
			var done = function () {
				var label = button.textContent;
				button.textContent = ( window.QuantumReady && window.QuantumReady.copied ) || 'Copied';
				setTimeout( function () { button.textContent = label; }, 1500 );
			};
			if ( navigator.clipboard && window.isSecureContext ) {
				navigator.clipboard.writeText( field.value ).then( done );
			} else {
				field.select();
				document.execCommand( 'copy' );
				done();
			}
		} );
	} );
}() );
