import {Maximize2, X} from 'lucide-react';
import {useRef} from 'react';
import type {ReactNode} from 'react';

type Props = {
  /** Image rendered in the page. */
  children: ReactNode;
  /** Image rendered larger inside the dialog. */
  zoomed: ReactNode;
  label: string;
  className?: string;
};

/** Click / keyboard-activate an image to open it larger in a native <dialog>. */
export function ZoomImage({children, zoomed, label, className = ''}: Props) {
  const ref = useRef<HTMLDialogElement | null>(null);
  return (
    <>
      <button
        type="button"
        className={`rd-zoom ${className}`.trim()}
        onClick={() => ref.current?.showModal()}
        aria-label={`Open larger: ${label}`}
      >
        {children}
        <span className="rd-zoom-hint" aria-hidden="true"><Maximize2 size={13} /> Enlarge</span>
      </button>
      <dialog
        ref={ref}
        className="rd-dialog"
        aria-label={label}
        onClick={(e) => {
          if (e.target === ref.current) ref.current?.close();
        }}
      >
        <button type="button" className="rd-dialog-close" onClick={() => ref.current?.close()} aria-label="Close">
          <X size={18} />
        </button>
        <div className="rd-dialog-body">{zoomed}</div>
      </dialog>
    </>
  );
}
