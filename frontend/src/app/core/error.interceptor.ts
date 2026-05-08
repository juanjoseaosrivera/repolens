import { HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';

/**
 * Global HTTP error interceptor.
 * Logs errors and re-throws so feature-level handlers can decide the UX.
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  return next(req).pipe(
    catchError((error) => {
      console.error(`[HTTP ${error.status}] ${req.method} ${req.url}`, error);
      return throwError(() => error);
    }),
  );
};
