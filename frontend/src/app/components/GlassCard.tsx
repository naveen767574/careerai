import { motion } from 'motion/react';
import { ReactNode, forwardRef } from 'react';

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  gradient?: 'blue' | 'purple' | 'cyan' | 'none';
  onClick?: () => void;
  onDragOver?: (e: React.DragEvent) => void;
  onDragLeave?: () => void;
  onDrop?: (e: React.DragEvent) => void;
}

export const GlassCard = forwardRef<HTMLDivElement, GlassCardProps>(
  ({ children, className = '', hover = false, gradient = 'none', onClick, onDragOver, onDragLeave, onDrop }, ref) => {
    const gradientStyles = {
      blue: 'bg-gradient-to-br from-blue-500/10 to-transparent',
      purple: 'bg-gradient-to-br from-purple-500/10 to-transparent',
      cyan: 'bg-gradient-to-br from-cyan-500/10 to-transparent',
      none: '',
    };

    return (
      <motion.div
        ref={ref}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        whileHover={hover ? { y: -4 } : {}}
        className={`glass-card ${hover ? 'glass-card-hover' : ''} rounded-2xl p-6 ${gradientStyles[gradient]} ${className}`}
        onClick={onClick}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        {children}
      </motion.div>
    );
  }
);
