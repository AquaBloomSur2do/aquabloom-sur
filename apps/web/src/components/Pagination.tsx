import React from 'react';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  onPageChange,
}) => {
  if (totalPages <= 1) return null;

  const handlePrevious = () => {
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (currentPage < totalPages) {
      onPageChange(currentPage + 1);
    }
  };

  return (
    <div className="flex items-center justify-center space-x-4 my-4">
      <button
        type="button"
        onClick={handlePrevious}
        disabled={currentPage <= 1}
        className="px-4 py-2 bg-gray-200 rounded disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
      >
        Página anterior
      </button>
      
      <span className="text-sm font-medium">
        Página {currentPage} de {totalPages}
      </span>

      <button
        type="button"
        onClick={handleNext}
        disabled={currentPage >= totalPages}
        className="px-4 py-2 bg-gray-200 rounded disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
      >
        Página siguiente
      </button>
    </div>
  );
};
