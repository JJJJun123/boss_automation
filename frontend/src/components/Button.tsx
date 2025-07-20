import React from 'react';
import classNames from 'classnames';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
}

const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  className,
  disabled,
  ...props
}) => {
  const baseClasses = classNames(
    'inline-flex items-center justify-center font-medium',
    'rounded-2xl transition-all duration-200',
    'focus:outline-none focus:ring-2 focus:ring-opacity-50',
    'transform active:scale-95',
    'disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none',
    {
      // Variants
      'btn-primary': variant === 'primary',
      'btn-secondary': variant === 'secondary',
      'bg-transparent hover:bg-gray-100 dark:hover:bg-dark-200 text-gray-700 dark:text-dark-700': variant === 'ghost',
      
      // Sizes
      'px-4 py-2 text-sm': size === 'sm',
      'px-6 py-3 text-base': size === 'md',
      'px-8 py-4 text-lg': size === 'lg',
      
      // States
      'hover:scale-105': !disabled && !loading,
      'cursor-not-allowed': disabled || loading,
    },
    className
  );

  return (
    <button
      className={baseClasses}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <div className="flex items-center">
          <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
          加载中...
        </div>
      ) : (
        <>
          {icon && <span className="mr-2">{icon}</span>}
          {children}
        </>
      )}
    </button>
  );
};

export default Button;