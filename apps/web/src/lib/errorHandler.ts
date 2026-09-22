import axios from 'axios';
import type { NavigateFunction } from 'react-router-dom';

export const setupGlobalErrorHandler = (navigate: NavigateFunction) => {
  axios.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response) {
        const status = error.response.status;
        
        if (status === 401) {
          navigate('/401');
        } else if (status === 403) {
          navigate('/403');
        }
      }
      return Promise.reject(error);
    }
  );
};
