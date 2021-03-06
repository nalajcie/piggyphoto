from __future__ import print_function
# piggyphoto.py
# Copyright (C) 2010 Alex Dumitrache
# Copyright (C) 2012, 2013 Marian Beermann
# Based on:
# - a small code example by Mario Boikov,
#   http://pysnippet.blogspot.com/2009/12/when-ctypes-comes-to-rescue.html
# - libgphoto2 Python bindings by David PHAM-VAN <david@ab2r.com>
# - ctypes_gphoto2.py by Hans Ulrich Niedermann <gp@n-dimensional.de>

import sys
import os
import re
import ctypes
import time
from ctypes import byref, util as ctype_util
from . import ptp

# Some functions return errors which can be fixed by retrying.
# For example, capture_preview on Canon 550D fails the first
# time, but subsequent calls are OK. Retries are performed on:
# camera.capture_preview, camera.capture_image and camera.init()
retries = 1

# This is run if gp_camera_init returns -60 (Could not lock the device) and retries >= 1.
# It unmounts all fs related to gphoto2. If one mounts his camera with gphoto2 gvfs, then
# it locks the device.
unmount_cmd = 'gvfs-mount -s gphoto2'

libgphoto2dll = ctype_util.find_library("gphoto2")

if libgphoto2dll is None:
    print("libgphoto2 library not found")
    sys.exit(-1)

print("Loading libgphoto2 DLL: " + libgphoto2dll)
gp = ctypes.CDLL(libgphoto2dll)
# Needed to ensure context memory address is not truncated to 32 bits
gp.gp_context_new.restype = ctypes.c_void_p

context = ctypes.c_void_p(gp.gp_context_new())


def library_version(verbose=True):
    gp.gp_library_version.restype = ctypes.POINTER(ctypes.c_char_p)
    if not verbose:
        arrText = gp.gp_library_version(GP_VERSION_SHORT)
    else:
        arrText = gp.gp_library_version(GP_VERSION_VERBOSE)

    v = ''
    for s in arrText:
        if s is None:
            break
        v += '%s\n' % s
    return v

# ctypes.c_char_p = c_char_p


# gphoto structures
class CameraFilePath(ctypes.Structure):
    """ From 'gphoto2-camera.h'
    typedef struct {
            char name [128];
            char folder [1024];
    } CameraFilePath;
    """
    _fields_ = [('name', (ctypes.c_char * 128)),
                ('folder', (ctypes.c_char * 1024))]


class CameraText(ctypes.Structure):
    _fields_ = [('text', (ctypes.c_char * (32 * 1024)))]

# cdef extern from "gphoto2/gphoto2-port-version.h":
#  ctypedef enum GPVersionVerbosity:
GP_VERSION_SHORT = 0
GP_VERSION_VERBOSE = 1

# cdef extern from "gphoto2/gphoto2-abilities-list.h":
#  ctypedef enum CameraDriverStatus:
GP_DRIVER_STATUS_PRODUCTION = 0
GP_DRIVER_STATUS_TESTING = 1
GP_DRIVER_STATUS_EXPERIMENTAL = 2
GP_DRIVER_STATUS_DEPRECATED = 3

#  ctypedef enum CameraOperation:
GP_OPERATION_NONE = 0
GP_OPERATION_CAPTURE_IMAGE = 1
GP_OPERATION_CAPTURE_VIDEO = 2
GP_OPERATION_CAPTURE_AUDIO = 3
GP_OPERATION_CAPTURE_PREVIEW = 4
GP_OPERATION_CONFIG = 5

#  ctypedef enum CameraFileOperation:
GP_FILE_OPERATION_NONE = 0
GP_FILE_OPERATION_DELETE = 1
GP_FILE_OPERATION_PREVIEW = 2
GP_FILE_OPERATION_RAW = 3
GP_FILE_OPERATION_AUDIO = 4
GP_FILE_OPERATION_EXIF = 5

#  ctypedef enum CameraFolderOperation:
GP_FOLDER_OPERATION_NONE = 0
GP_FOLDER_OPERATION_DELETE_ALL = 1
GP_FOLDER_OPERATION_PUT_FILE = 2
GP_FOLDER_OPERATION_MAKE_DIR = 3
GP_FOLDER_OPERATION_REMOVE_DIR = 4

# cdef extern from "gphoto2/gphoto2-port-info-list.h":
#  ctypedef enum GPPortType:
GP_PORT_NONE = 0
GP_PORT_SERIAL = 1
GP_PORT_USB = 2


class _CameraAbilities(ctypes.Structure):
    _fields_ = [('model', (ctypes.c_char * 128)),
                ('status', ctypes.c_int),
                ('port', ctypes.c_int),
                ('speed', (ctypes.c_int * 64)),
                ('operations', ctypes.c_int),
                ('file_operations', ctypes.c_int),
                ('folder_operations', ctypes.c_int),
                ('usb_vendor', ctypes.c_int),
                ('usb_product', ctypes.c_int),
                ('usb_class', ctypes.c_int),
                ('usb_subclass', ctypes.c_int),
                ('usb_protocol', ctypes.c_int),
                ('library', (ctypes.c_char * 1024)),
                ('id', (ctypes.c_char * 1024)),
                ('device_type', ctypes.c_int),
                ('reserved2', ctypes.c_int),
                ('reserved3', ctypes.c_int),
                ('reserved4', ctypes.c_int),
                ('reserved5', ctypes.c_int),
                ('reserved6', ctypes.c_int),
                ('reserved7', ctypes.c_int),
                ('reserved8', ctypes.c_int)]

# the GPPortInfo data structure is a pointer in SVN
# in stable versions, it is a struct
if library_version().split('\n')[0] == '2.4.99':
    class PortInfo(ctypes.c_void_p):
        pass
else:
    class PortInfo(ctypes.Structure):
        _fields_ = [
            ('type', ctypes.c_int),  # enum is 32 bits on 32 and 64 bit Linux
            ('name', (ctypes.c_char * 64)),
            ('path', (ctypes.c_char * 64)),
            ('library_filename', (ctypes.c_char * 1024))
            ]

# gphoto constants
# Defined in 'gphoto2-port-result.h'
GP_OK = 0
# CameraCaptureType enum in 'gphoto2-camera.h'
GP_CAPTURE_IMAGE = 0
# CameraFileType enum in 'gphoto2-file.h'
GP_FILE_TYPE_NORMAL = 1


GP_WIDGET_WINDOW = 0   # Window widget This is the toplevel configuration widget. It should likely contain multiple GP_WIDGET_SECTION entries.
GP_WIDGET_SECTION = 1  # Section widget (think Tab).
GP_WIDGET_TEXT = 2     # Text widget.
GP_WIDGET_RANGE = 3    # Slider widget.
GP_WIDGET_TOGGLE = 4   # Toggle widget (think check box).
GP_WIDGET_RADIO = 5    # Radio button widget.
GP_WIDGET_MENU = 6     # Menu widget (same as RADIO).
GP_WIDGET_BUTTON = 7   # Button press widget.
GP_WIDGET_DATE = 8     # Date entering widget.
widget_types = ['Window', 'Section', 'Text', 'Range', 'Toggle', 'Radio', 'Menu', 'Button', 'Date']


# Unused
class _CameraWidget(ctypes.Structure):
    _fields_ = [('type', ctypes.c_int),
                ('label', (ctypes.c_char * 256)),
                ('info', (ctypes.c_char * 1024)),
                ('name', (ctypes.c_char * 256)),
                ('parent', (ctypes.c_void_p)),
                ('value_string', ctypes.c_char_p),
                ('value_int', ctypes.c_int),
                ('value_float', ctypes.c_float),
                ('choice', (ctypes.c_void_p)),
                ('choice_count', ctypes.c_int),
                ('min', ctypes.c_float),
                ('max', ctypes.c_float),
                ('increment', ctypes.c_float),
                ('children', (ctypes.c_void_p)),
                ('children_count', (ctypes.c_int)),
                ('changed', (ctypes.c_int)),
                ('readonly', (ctypes.c_int)),
                ('ref_count', (ctypes.c_int)),
                ('id', (ctypes.c_int)),
                ('callback', (ctypes.c_void_p))]


class libgphoto2error(Exception):
    def __init__(self, result, message):
        self.result = result
        self.message = message

    def __str__(self):
        return "%s (%s)" % (self.message, self.result)


def _check_result(result):
    if result < 0:
        gp.gp_result_as_string.restype = ctypes.c_char_p
        message = gp.gp_result_as_string(result)
        raise libgphoto2error(result, message)
    return result


def _check_unref(result, camfile):
    if result != 0:
        gp.gp_file_unref(camfile._cf)
        gp.gp_result_as_string.restype = ctypes.c_char_p
        message = gp.gp_result_as_string(result)
        raise libgphoto2error(result, message)


class Camera(object):
    def __init__(self, auto_init=True):
        self._cam = ctypes.c_void_p()
        self._leave_locked = False
        _check_result(gp.gp_camera_new(byref(self._cam)))
        self.initialized = False
        if auto_init:
            self.init()

    def init(self):
        if self.initialized:
            print("Camera is already initialized.")
        ans = 0
        for i in xrange(1 + retries):
            ans = gp.gp_camera_init(self._cam, context)
            if ans == 0:
                break
            elif ans == -60:
                print("***", unmount_cmd)
                os.system(unmount_cmd)
                time.sleep(1)
                print("Camera.init() retry #%d..." % (i))
        _check_result(ans)
        self.initialized = True

    def reinit(self):
        self.close()
        self.__new__()
        self.init()

    def __del__(self):
        # not sure about this one - why would you use it
        if not self._leave_locked:
            self.close()

    def __enter__(self):
        return self

    def __exit__(self):
        self.close()

    def leave_locked(self):
        self._leave_locked = True

    def ref(self):
        _check_result(gp.gp_camera_ref(self._cam))

    def unref(self):
        _check_result(gp.gp_camera_unref(self._cam))

    def _exit(self):
        _check_result(gp.gp_camera_exit(self._cam, context))

    def _free(self):
        _check_result(gp.gp_camera_free(self._cam))

    def close(self):
        if self.initialized:
            self._exit()
            self._free()
            self.initialized = False

    @property
    def summary(self):
        txt = CameraText()
        _check_result(gp.gp_camera_get_summary(self._cam, byref(txt), context))
        return txt.text.decode("utf-8")

    @property
    def manual(self):
        # TODO: CHECK FOR ERROR ON CALL
        txt = CameraText()
        _check_result(gp.gp_camera_get_manual(self._cam, byref(txt), context))
        return txt.text.decode("utf-8")

    @property
    def about(self):
        txt = CameraText()
        _check_result(gp.gp_camera_get_about(self._cam, byref(txt), context))
        return txt.text.decode("utf-8")

    @property
    def abilities(self):
        ab = CameraAbilities()
        _check_result(gp.gp_camera_get_abilities(self._cam, byref(ab._ab)))
        return ab

    @abilities.setter
    def abilities(self, ab):
        _check_result(gp.gp_camera_set_abilities(self._cam, ab._ab))

    @property
    def config(self):
        window = CameraWidget(GP_WIDGET_WINDOW)
        _check_result(gp.gp_camera_get_config(self._cam, byref(window._w), context))
        window.populate_children()
        return window

    @config.setter
    def config(self, window):
        _check_result(gp.gp_camera_set_config(self._cam, window._w, context))

    @property
    def port_info(self):
        raise NotImplementedError

    @port_info.setter
    def port_info(self, info):
        _check_result(gp.gp_camera_set_port_info(self._cam, info))

    def capture_image(self, destpath=None):
        path = CameraFilePath()

        ans = 0
        for i in xrange(1 + retries):
            ans = gp.gp_camera_capture(self._cam, GP_CAPTURE_IMAGE, byref(path), context)
            if ans == 0:
                break
            else:
                print("capture_image(%s) retry #%d..." % (destpath, i))
        _check_result(ans)

        if destpath:
            self.download_file(path.folder, path.name, destpath)
        else:
            return (path.folder, path.name)

    def capture_preview(self, destpath=None):
        """
        Note: ALWAYS use cfile.unref() after usage
        """
        cfile = CameraFile()

        ans = 0
        for i in xrange(1 + retries):
            ans = gp.gp_camera_capture_preview(self._cam, cfile._cf, context)
            if ans == 0:
                break
            else:
                print("capture_preview(%s) retry #%d..." % (destpath, i))
        _check_result(ans)

        if destpath:
            cfile.save(destpath)
        return cfile

    def download_file(self, srcfolder, srcfilename, destpath):
        cfile = CameraFile(self._cam, srcfolder, srcfilename)
        cfile.save(destpath)
        gp.gp_file_unref(cfile._cf)

    def trigger_capture(self):
        _check_result(gp.gp_camera_trigger_capture(self._cam, context))

    def wait_for_event(self, timeout):
        raise NotImplementedError

    def list_folders(self, path="/"):
        l = CameraList()
        _check_result(gp.gp_camera_folder_list_folders(self._cam, str(path), l._l, context))
        return l.toList()

    def list_files(self, path="/"):
        l = CameraList()
        _check_result(gp.gp_camera_folder_list_files(self._cam, str(path), l._l, context))
        return l.toList()

    def _list_config(self, widget, cfglist, path):
        children = widget.children
        if children:
            for c in children:
                self._list_config(c, cfglist, path + "." + c.name)
        else:
            widget.dump(path)
            cfglist.append(path)

    def list_config(self):
        cfglist = []
        cfg = self.config
        self._list_config(cfg, cfglist, cfg.name)
        return cfglist

    def ptp_canon_eos_requestdevicepropvalue(self, prop):
        params = ctypes.c_void_p(self._cam.value + 12)
        gp.ptp_generic_no_data(params, ptp.PTP_OC_CANON_EOS_RequestDevicePropValue, 1, prop)

    # TODO: port_speed, init, config


class CameraFile(object):
    def __init__(self, cam=None, srcfolder=None, srcfilename=None):
        self._cf = ctypes.c_void_p()
        _check_result(gp.gp_file_new(byref(self._cf)))
        if cam:
            _check_unref(gp.gp_camera_file_get(
                cam, srcfolder, srcfilename, GP_FILE_TYPE_NORMAL, self._cf, context), self)

    def open(self, filename):
        _check_result(gp.gp_file_open(byref(self._cf), filename))

    def save(self, filename=None):
        if filename is None:
            filename = self.name

        # deprecated as of libgphoto2 2.5.0
        # _check_result(gp.gp_file_save(self._cf, filename))

        file = open(filename, 'wb')
        file.write(self.to_pixbuf())
        file.close()

    def get_data(self):
        data = ctypes.pointer(ctypes.c_char())
        size = ctypes.c_ulong()
        _check_result(gp.gp_file_get_data_and_size(
            self._cf,
            ctypes.byref(data),
            ctypes.byref(size)))
        return ctypes.string_at(data, size.value)

    def ref(self):
        _check_result(gp.gp_file_ref(self._cf))

    def unref(self):
        _check_result(gp.gp_file_unref(self._cf))

    def clean(self):
        _check_result(gp.gp_file_clean(self._cf))

    def copy(self, source):
        _check_result(gp.gp_file_copy(self._cf, source._cf))

    # do we need this?
    def to_pixbuf(self):
        mimetype = ctypes.c_char_p()
        gp.gp_file_get_mime_type(self._cf, ctypes.byref(mimetype))
        print(ctypes.string_at(mimetype))

        """Returns data for GdkPixbuf.PixbufLoader.write()."""
        data = ctypes.c_char_p()
        size = ctypes.c_ulong()
        gp.gp_file_get_data_and_size(self._cf, ctypes.byref(data),
                                     ctypes.byref(size))

        print(size.value)
        return ctypes.string_at(data, size.value)

    def __dealoc__(self, filename):
        _check_result(gp.gp_file_free(self._cf))

    @property
    def name(self):
        name = ctypes.c_char_p()
        _check_result(gp.gp_file_get_name(self._cf, byref(name)))
        return name.value.decode("utf-8")

    @name.setter
    def name(self, name):
        _check_result(gp.gp_file_set_name(self._cf, str(name)))

    def __del__(self):
        self.unref()

    # TODO: new_from_fd (?), new_from_handler (?), mime_tipe, mtime,
    # detect_mime_type, adjust_name_for_mime_type, data_and_size,
    # append, slurp, python file object?


class CameraAbilitiesList(object):
    _static_l = None

    def __init__(self):
        if CameraAbilitiesList._static_l is None:
            CameraAbilitiesList._static_l = ctypes.c_void_p()
            _check_result(gp.gp_abilities_list_new(byref(CameraAbilitiesList._static_l)))
            _check_result(gp.gp_abilities_list_load(CameraAbilitiesList._static_l, context))
        self._l = CameraAbilitiesList._static_l

    def __del__(self):
        # don't free, since it is only created once
        # _check_result(gp.gp_abilities_list_free(self._l))
        pass

    def detect(self, il, l):
        _check_result(gp.gp_abilities_list_detect(self._l, il._l, l._l, context))

    def lookup_model(self, model):
        return _check_result(gp.gp_abilities_list_lookup_model(self._l, model))

    def get_abilities(self, model_index, ab):
        _check_result(gp.gp_abilities_list_get_abilities(self._l, model_index, byref(ab._ab)))


class CameraAbilities(object):
    def __init__(self):
        self._ab = _CameraAbilities()

    def __repr__(self):
        return ("Model : %s\nStatus : %d\nPort : %d\nOperations : %d\nFile Operations : %d\n" + \
            "Folder Operations : %d\nUSB (vendor/product) : 0x%x/0x%x\nUSB class : 0x%x/0x%x/0x%x\n" + \
            "Library : %s\nId : %s\n") % \
            (self.model, self._ab.status, self._ab.port, self._ab.operations,
                self._ab.file_operations, self._ab.folder_operations,
                self._ab.usb_vendor, self._ab.usb_product, self._ab.usb_class,
                self._ab.usb_subclass, self._ab.usb_protocol, self.library, self.id)

    model = property(lambda self: self._ab.model.decode("utf-8"), None)
    status = property(lambda self: self._ab.status, None)
    port = property(lambda self: self._ab.port, None)
    operations = property(lambda self: self._ab.operations, None)
    file_operations = property(lambda self: self._ab.file_operations, None)
    folder_operations = property(lambda self: self._ab.folder_operations, None)
    usb_vendor = property(lambda self: self._ab.usb_vendor, None)
    usb_product = property(lambda self: self._ab.usb_product, None)
    usb_class = property(lambda self: self._ab.usb_class, None)
    usb_subclass = property(lambda self: self._ab.usb_subclass, None)
    usb_protocol = property(lambda self: self._ab.usb_protocol, None)
    library = property(lambda self: self._ab.library.decode("utf-8"), None)
    id = property(lambda self: self._ab.id.decode("utf-8"), None)


class PortInfoList(object):
    _static_l = None

    def __init__(self):
        if PortInfoList._static_l is None:
            PortInfoList._static_l = ctypes.c_void_p()
            _check_result(gp.gp_port_info_list_new(byref(PortInfoList._static_l)))
            _check_result(gp.gp_port_info_list_load(PortInfoList._static_l))
        self._l = PortInfoList._static_l

    def __del__(self):
        # don't free, since it is only created once
        # _check_result(gp.gp_port_info_list_free(self._l))
        pass

    def count(self):
        c = gp.gp_port_info_list_count(self._l)
        _check_result(c)
        return c

    def lookup_path(self, path):
        index = gp.gp_port_info_list_lookup_path(self._l, path)
        _check_result(index)
        return index

    def get_info(self, path_index):
        info = PortInfo()
        _check_result(gp.gp_port_info_list_get_info(self._l, path_index, byref(info)))
        return info


class CameraList(object):
    def __init__(self, autodetect=False):
        self._l = ctypes.c_void_p()
        _check_result(gp.gp_list_new(byref(self._l)))

        if autodetect:
            if hasattr(gp, 'gp_camera_autodetect'):
                gp.gp_camera_autodetect(self._l, context)
            else:
                # this is for stable versions of gphoto <= 2.4.10.1
                xlist = CameraList()
                il = PortInfoList()
                il.count()
                al = CameraAbilitiesList()
                al.detect(il, xlist)

                # begin USB bug code
                # with libgphoto 2.4.8, sometimes one attached camera returns
                # one path "usb:" and sometimes two paths "usb:" and "usb:xxx,yyy"
                good_list = []
                bad_list = []
                for i in xrange(xlist.count()):
                    model = xlist.get_name(i)
                    path = xlist.get_value(i)
                    if re.match(r'usb:\d{3},\d{3}', path):
                        good_list.append((model, path))
                    elif path == 'usb:':
                        bad_list.append((model, path))
                if len(good_list):
                    for model, path in good_list:
                        self.append(model, path)
                elif len(bad_list) == 1:
                    model, path = bad_list[0]
                    self.append(model, path)
                # end USB bug code

                del al
                del il
                del xlist

    def ref(self):
        _check_result(gp.gp_list_ref(self._l))

    def unref(self):
        _check_result(gp.gp_list_ref(self._l))

    def __del__(self):
        # this failed once in gphoto 2.4.6
        _check_result(gp.gp_list_free(self._l))
        pass

    def reset(self):
        _check_result(gp.gp_list_reset(self._l))

    def append(self, name, value):
        _check_result(gp.gp_list_append(self._l, str(name), str(value)))

    def sort(self):
        _check_result(gp.gp_list_sort(self._l))

    def count(self):
        return _check_result(gp.gp_list_count(self._l))

    def find_by_name(self, name):
        index = ctypes.c_int()
        _check_result(gp.gp_list_find_by_name(self._l, byref(index), str(name)))
        return index.value

    def get_name(self, index):
        name = ctypes.c_char_p()
        _check_result(gp.gp_list_get_name(self._l, int(index), byref(name)))
        return name.value.decode("utf-8")

    def get_value(self, index):
        value = ctypes.c_char_p()
        _check_result(gp.gp_list_get_value(self._l, int(index), byref(value)))
        return value.value.decode("utf-8")

    def set_name(self, index, name):
        _check_result(gp.gp_list_set_name(self._l, int(index), str(name)))

    def set_value(self, index, value):
        _check_result(gp.gp_list_set_value(self._l, int(index), str(value)))

    def __str__(self):
        header = "CameraList object with %d elements:\n" % self.count()
        contents = ["%d: (%s, %s)" % (i, self.get_name(i), self.get_value(i))
                    for i in xrange(self.count())]

        return header + '\n'.join(contents)

    def toList(self):
        return [(self.get_name(i), self.get_value(i)) for i in xrange(self.count())]
        xlist = []
        for i in xrange(self.count()):
            n, v = self.get_name(i), self.get_value(i)
            if v is None:
                xlist.append(n)
            else:
                xlist.append((n, v))
        return xlist

    def toDict(self):
        return dict(self.toList())


class CameraWidget(object):

    def __init__(self, type=None, label=""):
        self._w = ctypes.c_void_p()
        if type is not None:
            _check_result(gp.gp_widget_new(int(type), str(label), byref(self._w)))
            _check_result(gp.gp_widget_ref(self._w))
        else:
            self._w = ctypes.c_void_p()

    def __repr__(self):
        return "%s:%s:%s:%s:%s" % (self.label, self.name, self.info, self.typestr, self.value)

    def ref(self):
        _check_result(gp.gp_widget_ref(self._w))

    def unref(self):
        _check_result(gp.gp_widget_unref(self._w))

    def __del__(self):
        # TODO: fix this or find a good reason not to
        # print "widget(%s) __del__" % self.name
        # _check_result(gp.gp_widget_unref(self._w))
        pass

    @property
    def info(self):
        info = ctypes.c_char_p()
        _check_result(gp.gp_widget_get_info(self._w, byref(info)))
        return info.value.decode("utf-8")

    @info.setter
    def info(self, info):
        _check_result(gp.gp_widget_set_info(self._w, str(info)))

    @property
    def name(self):
        name = ctypes.c_char_p()
        _check_result(gp.gp_widget_get_name(self._w, byref(name)))
        return name.value.decode("utf-8")

    @name.setter
    def name(self, name):
        _check_result(gp.gp_widget_set_name(self._w, str(name)))

    @property
    def id(self):
        id = ctypes.c_int()
        _check_result(gp.gp_widget_get_id(self._w, byref(id)))
        return id.value

    @property
    def changed(self):
        return gp.gp_widget_changed(self._w)

    @changed.setter
    def _set_changed(self, changed):
        _check_result(gp.gp_widget_set_changed(self._w, str(changed)))

    @property
    def readonly(self):
        readonly = ctypes.c_int()
        _check_result(gp.gp_widget_get_readonly(self._w, byref(readonly)))
        return readonly.value

    @readonly.setter
    def readonly(self, readonly):
        _check_result(gp.gp_widget_set_readonly(self._w, int(readonly)))

    @property
    def type(self):
        type = ctypes.c_int()
        _check_result(gp.gp_widget_get_type(self._w, byref(type)))
        return type.value

    @property
    def typestr(self):
        return widget_types[self.type]

    @property
    def label(self):
        label = ctypes.c_char_p()
        _check_result(gp.gp_widget_get_label(self._w, byref(label)))
        return label.value.decode("utf-8")

    @label.setter
    def label(self, label):
        _check_result(gp.gp_widget_set_label(self._w, str(label)))

    @property
    def value(self):
        value = ctypes.c_void_p()
        ans = gp.gp_widget_get_value(self._w, byref(value))
        _check_result(ans)

        if self.type in [GP_WIDGET_MENU, GP_WIDGET_RADIO, GP_WIDGET_TEXT]:
            v = ctypes.cast(value.value, ctypes.c_char_p).value
            if v is not None:
                return v.decode("utf-8")
            return ""
        elif self.type == GP_WIDGET_RANGE:
            lower, upper, step = ctypes.c_float(), ctypes.c_float(), ctypes.c_float()
            gp.gp_widget_get_range(self._w, byref(lower), byref(upper), byref(step))

            return (lower.value, upper.value, step.value)
        elif self.type in [GP_WIDGET_TOGGLE, GP_WIDGET_DATE]:
            return ctypes.cast(ctypes.addressof(value), ctypes.POINTER(ctypes.c_int))[0]
        else:
            return None

    @value.setter
    def value(self, value):
        if self.type in (GP_WIDGET_MENU, GP_WIDGET_RADIO, GP_WIDGET_TEXT):
            value = ctypes.c_char_p(value)
        elif self.type == GP_WIDGET_RANGE:
            # According to libgphoto 2.5 docs ( http://enkore.de/libgphoto2-docs/ )
            # "Please pass (char*) for GP_WIDGET_MENU, GP_WIDGET_TEXT, GP_WIDGET_RADIO,
            #  (float) for GP_WIDGET_RANGE, (int) for GP_WIDGET_DATE, GP_WIDGET_TOGGLE,
            #  and (CameraWidgetCallback) for GP_WIDGET_BUTTON.
            # So this should probably work.
            value = byref(ctypes.c_float(value))
        elif self.type in (GP_WIDGET_TOGGLE, GP_WIDGET_DATE):
            value = byref(ctypes.c_int(value))
        else:
            raise NotImplementedError()

        _check_result(gp.gp_widget_set_value(self._w, value))

    def append(self, child):
        _check_result(gp.gp_widget_append(self._w, child._w))

    def prepend(self, child):
        _check_result(gp.gp_widget_prepend(self._w, child._w))

    def count_children(self):
        return gp.gp_widget_count_children(self._w)

    def get_child(self, child_number):
        w = CameraWidget()
        _check_result(gp.gp_widget_get_child(self._w, int(child_number), byref(w._w)))
        _check_result(gp.gp_widget_ref(w._w))
        return w

    def get_child_by_label(self, label):
        w = CameraWidget()
        _check_result(gp.gp_widget_get_child_by_label(self._w, str(label), byref(w._w)))
        return w

    def get_child_by_id(self, id):
        w = CameraWidget()
        _check_result(gp.gp_widget_get_child_by_id(self._w, int(id), byref(w._w)))
        return w

    def get_child_by_name(self, name):
        w = CameraWidget()
        # this fails in 2.4.6 (Ubuntu 9.10)
        _check_result(gp.gp_widget_get_child_by_name(self._w, str(name), byref(w._w)))
        return w

    @property
    def children(self):
        children = []
        for i in xrange(self.count_children()):
            children.append(self.get_child(i))
        return children

    @property
    def parent(self):
        w = CameraWidget()
        _check_result(gp.gp_widget_get_parent(self._w, byref(w._w)))
        return w

    @property
    def root(self):
        w = CameraWidget()
        _check_result(gp.gp_widget_get_root(self._w, byref(w._w)))
        return w

    @property
    def range(self):
        """CameraWidget.range => (min, max, increment)"""
        min, max, increment = ctypes.c_float(), ctypes.c_float(), ctypes.c_float()
        _check_result(gp.gp_widget_set_range(
            self._w,
            byref(min),
            byref(max),
            byref(increment)))
        return (min.value, max.value, increment.value)

    @range.setter
    def range(self, range):
        """CameraWidget.range = (min, max, increment)"""
        float = ctypes.c_float
        min, max, increment = range
        _check_result(gp.gp_widget_set_range(
            self._w,
            float(min),
            float(max),
            float(increment)))

    def add_choice(self, choice):
        _check_result(gp.gp_widget_add_choice(self._w, str(choice)))

    def count_choices(self):
        return gp.gp_widget_count_choices(self._w)

    def get_choice(self, choice_number):
        choice = ctypes.c_char_p()
        _check_result(
            gp.gp_widget_get_choice(
                self._w, int(choice_number),
                byref(choice)))
        return choice.value.decode("utf-8")

    @property
    def choices(self):
        choices = []
        for i in range(self.count_choices()):
            choices.append(self.get_choice(i))
        return choices

    def createdoc(self):
        label = "Label: " + self.label
        info = "Info: " + (self.info if self.info != "" else "n/a")
        type = "Type: " + self.typestr
        childs = []
        for c in self.children:
            childs.append("  - " + c.name + ": " + c.label)
        if len(childs):
            childstr = "Children:\n" + '\n'.join(childs)
            return label + "\n" + info + "\n" + type + "\n" + childstr
        else:
            return label + "\n" + info + "\n" + type

    def _pop(widget, simplewidget):
        for c in widget.children:
            simplechild = CameraWidgetSimple()
            if c.count_children():
                setattr(simplewidget, c.name, simplechild)
                simplechild.__doc__ = c.createdoc()
                c._pop(simplechild)
            else:
                setattr(simplewidget, c.name, c)

    def populate_children(self):
        simplewidget = CameraWidgetSimple()
        setattr(self, self.name, simplewidget)
        simplewidget.__doc__ = self.createdoc()
        self._pop(simplewidget)

    def dump(self, path):
        value = str(self.value)
        label = str(self.label)

        space = 60 - len(value) - 2
        print("%-40s = %s%s" % (path, value, ("(%s)" % label).rjust(space)))

        if self.type in [GP_WIDGET_MENU, GP_WIDGET_RADIO, GP_WIDGET_TEXT] \
                and self.choices:
            numeric = True
            for x in self.choices:
                try:
                    int(x)
                except ValueError:
                    numeric = False
                    break

            print("    ", end="")
            if numeric:
                lower, upper = int(self.choices[0]), int(self.choices[-1])
                r = range(lower, upper)
                count = 0

                for x in self.choices:
                    if int(x) in r:
                        count += 1

                if count == len(r):
                    print(" " * 55, "[%s .. %s]" % (lower, upper))
                else:
                    print(str(self.choices))
            else:
                print(str(self.choices))
        elif self.type == GP_WIDGET_RANGE:
            print(str(self.range))


class CameraWidgetSimple(object):
    pass
