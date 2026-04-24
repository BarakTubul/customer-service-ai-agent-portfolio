import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline';
  size?: 'sm' | 'md' | 'lg';
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  ...props
}: ButtonProps) {
  const baseClasses =
    'inline-flex items-center justify-center whitespace-nowrap rounded-lg font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-teal-200 disabled:opacity-60 disabled:pointer-events-none';

  const variantClasses = {
    primary: 'border border-teal-700 bg-teal-700 text-white shadow-sm hover:-translate-y-0.5 hover:bg-teal-800 hover:shadow-md',
    secondary: 'border border-orange-500 bg-orange-500 text-white shadow-sm hover:-translate-y-0.5 hover:bg-orange-600 hover:shadow-md',
    outline: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 hover:border-slate-400',
  };

  const sizeClasses = {
    sm: 'h-9 px-3 text-sm',
    md: 'h-11 px-4 text-sm',
    lg: 'h-12 px-6 text-base',
  };

  return (
    <button
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    />
  );
}

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  label?: string;
}

export function Input({ error, label, className = '', ...props }: InputProps) {
  return (
    <div className="w-full">
      {label && <label className="mb-1.5 block text-sm font-semibold text-slate-700">{label}</label>}
      <input
        className={`h-11 w-full rounded-lg border bg-white px-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-4 focus:ring-teal-200 ${
          error ? 'border-red-500' : 'border-slate-300 focus:border-teal-700'
        } ${className}`}
        {...props}
      />
      {error && <p className="mt-1.5 text-sm font-medium text-red-600">{error}</p>}
    </div>
  );
}

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function Card({ className = '', children, ...props }: CardProps) {
  return (
    <div
      className={`rounded-xl border border-slate-200 bg-white p-6 shadow-sm ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

interface AlertProps {
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  onClose?: () => void;
}

export function Alert({ type, message, onClose }: AlertProps) {
  const bgClasses = {
    success: 'bg-emerald-50 border-emerald-200',
    error: 'bg-red-50 border-red-200',
    info: 'bg-blue-50 border-blue-200',
    warning: 'bg-amber-50 border-amber-200',
  };

  const textClasses = {
    success: 'text-emerald-800',
    error: 'text-red-800',
    info: 'text-blue-800',
    warning: 'text-amber-800',
  };

  return (
    <div className={`${bgClasses[type]} ${textClasses[type]} flex items-start justify-between rounded-xl border p-4`}>
      <span className="pr-3 text-sm font-medium">{message}</span>
      {onClose && (
        <button onClick={onClose} className="rounded p-1 text-base font-bold leading-none hover:bg-black/5">
          ×
        </button>
      )}
    </div>
  );
}
