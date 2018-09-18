#
# Copyright 2017, Data61
# Commonwealth Scientific and Industrial Research Organisation (CSIRO)
# ABN 41 687 119 230.
#
# This software may be distributed and modified according to the terms of
# the BSD 2-Clause license. Note that NO WARRANTY is provided.
# See "LICENSE_BSD2.txt" for details.
#
# @TAG(DATA61_BSD)
#

from __future__ import print_function

import os
from jinja2 import contextfilter, contextfunction

import macros
import tutorialstate
from tutorialstate import TaskContentType
from capdl import seL4_TCBObject, seL4_EndpointObject, \
    seL4_NotificationObject, seL4_CanRead, seL4_CanWrite, seL4_AllRights, \
    seL4_ARM_SmallPageObject, seL4_FrameObject, seL4_IRQControl, \
    seL4_UntypedObject, seL4_IA32_IOPort, seL4_IA32_IOSpace, \
    seL4_ARM_IOSpace, seL4_ASID_Pool, \
    seL4_ARM_SectionObject, seL4_ARM_SuperSectionObject, \
    seL4_SchedContextObject, seL4_SchedControl, seL4_RTReplyObject

from pickle import load, dumps


@contextfilter
def File(context, content, filename):
    '''
    Declare content to be written directly to a file
    '''
    args = context['args']
    if args.out_dir and not args.docsite:
        filename = os.path.join(args.out_dir, filename)
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

        elf_file = open(filename, 'w')
        print(filename, file=args.output_files)
        elf_file.write(content)

    return content

@contextfunction
def ExternalFile(context, filename):
    '''
    Declare an additional file to be processed by the template renderer.
    '''
    state = context['state']
    state.additional_files.append(filename)
    return


@contextfilter
def TaskContent(context, content, task_name, content_type=TaskContentType.COMPLETED, subtask=None, completion=None):
    '''
    Declare task content for a task. Optionally takes content type argument
    '''
    state = context["state"]
    task = state.get_task(task_name)
    task.set_content(content_type, content, subtask)
    if completion:
        task.set_completion(content_type, completion)
    return content

@contextfilter
def TaskCompletion(context, content, task_name, content_type):
    '''
    Declare completion text for a particular content_type
    '''
    state = context["state"]
    task = state.get_task(task_name)
    task.set_completion(content_type, content)
    return content



@contextfilter
def ExcludeDocs(context, content):
    '''
    Hides the contents from the documentation. Side effects from other functions
    and filters will still occur
    '''
    return ""

@contextfunction
def include_task(context, task_name, subtask=None):
    '''
    Prints a task out
    '''
    state = context["state"]
    task = state.get_task(task_name)
    return state.print_task(task, subtask)


@contextfunction
def include_task_type_replace(context, task_names):
    '''
    Takes a list of task names and displays only the one that is
    active in the tutorial
    '''
    if not isinstance(task_names, list):
        task_names = [task_names]
    state = context["state"]
    previous_task = None
    previous_subtask = None

    for (i, name) in enumerate(task_names):
        subtask = None
        if isinstance(name,tuple):
            # Subclass
            subtask = name[1]
            name = name[0]
        task = state.get_task(name)
        if not state.is_current_task(task):
            previous_task = task
            previous_subtask = subtask

        else:
            try:
                content = state.print_task(task, subtask)
                return content

            except KeyError:
                # If the start of task isn't defined then we print the previous task
                if i > 0:
                    return state.print_task(previous_task, previous_subtask)
                else:
                    return ""


    raise Exception("Could not find thing")

@contextfunction
def include_task_type_append(context, task_names):
    '''
    Takes a list of task_names and appends the task content based on the position in
    the tutorial.
    '''
    if not isinstance(task_names, list):
        task_names = [task_names]
    args = context['args']
    state = context["state"]

    result = []
    for i in task_names:
        subtask = None
        if isinstance(i,tuple):
            # Subclass
            subtask = i[1]
            i = i[0]
        task = state.get_task(i)
        if task <= state.current_task:
            content = ""
            try:
                print(task.name)
                content = state.print_task(task, subtask)
            except KeyError:
                if state.solution:
                    raise # In solution mode we require content.

            result.append(content)
    return '\n'.join(result)


@contextfunction
def declare_task_ordering(context, task_names):
    '''
    Declare the list of tasks that the tutorial contains.
    Their ordering in the array implies their ordering in the tutorial.
    '''
    state = context['state']
    state.declare_tasks(task_names)
    args = context['args']
    if args.out_dir and not args.docsite:
        filename = os.path.join(args.out_dir,".tasks")
        print(filename, file=args.output_files)
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        task_file = open(filename, 'w')
        for i in task_names:
            print(i,file=task_file)
    return ""


@contextfunction
def RecordObject(context, object, name, cap_symbol=None, **kwargs):
    print("Cap registered")
    state = context['state']
    stash = state.stash
    write = []
    if name in stash.objects:
        assert stash.objects[name][0] is object
        stash.objects[name][1].update(kwargs)
    else:
        if object is seL4_FrameObject:
            stash.unclaimed_special_pages.append((kwargs['symbol'], kwargs['size'], kwargs['alignment'], kwargs['section']))
            write.append("extern const void *%s;\n" % kwargs['symbol'])
        elif object is not None:
            stash.objects[name] = (object, kwargs)

    stash.unclaimed_caps.append((cap_symbol, name, kwargs))
    if cap_symbol:
        write.append("extern seL4_CPtr %s;" % cap_symbol)
    return "\n".join(write)

@contextfunction
def capdl_my_cspace(context, elf_name, cap_symbol):
    return RecordObject(context, None, "cnode_%s" % elf_name, cap_symbol=cap_symbol)

@contextfunction
def capdl_my_vspace(context, elf_name, cap_symbol):
    return RecordObject(context, None, "vspace_%s" % elf_name, cap_symbol=cap_symbol)

@contextfunction
def capdl_empty_slot(context, cap_symbol):
    return RecordObject(context, None, None, cap_symbol=cap_symbol)


@contextfilter
def ELF(context, content, name):
    '''
    Declares a ELF object containing content with name.
    '''
    print("here")
    state = context['state']
    args = context['args']
    stash = state.stash

    print(content, name, context)
    if args.out_dir and not args.docsite:
        filename = os.path.join(args.out_dir, "%s.c" % name)
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

        elf_file = open(filename, 'w')
        print(filename, file=args.output_files)

        elf_file.write(content)
        # elf_file.write("#line 1 \"thing\"\n" + content)

        stash.caps[name] = stash.unclaimed_caps
        stash.unclaimed_caps = []
        stash.elfs[name] = {"filename" :"%s.c" % name}
        stash.special_pages[name] = [("stack", 16*0x1000, 0x1000, 'guarded'),
        ("mainIpcBuffer", 0x1000, 0x1000, 'guarded'),
        ] + stash.unclaimed_special_pages
        stash.unclaimed_special_pages = []

    print("end")
    return content

@contextfunction
def write_manifest(context, file='manifest.py'):
    state = context['state']
    args = context['args']
    stash = state.stash
    if args.out_dir and not args.docsite:
        filename = os.path.join(args.out_dir, file)
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

        file = open(filename, 'w')
        print(filename, file=args.output_files)


        manifest = """
import pickle

serialised = \"\"\"%s\"\"\"

# (OBJECTS, CSPACE_LAYOUT, SPECIAL_PAGES) = pickle.loads(serialised)
# print((OBJECTS, CSPACE_LAYOUT, SPECIAL_PAGES))
print(serialised)

        """
        file.write(manifest % dumps((stash.objects, stash.caps, stash.special_pages)))
    return ""



'''
These are for potential extra template functions, that haven't been required
by templating requirements yet.
@contextfunction
def show_if_task(context, task_names):
    pass

@contextfunction
def show_before_task(context, task_names):
    pass


@contextfunction
def show_after_task(context, task_names):
    pass

@contextfunction
def hide_if_task(context, task_names):
    pass

@contextfunction
def hide_before_task(context, task_names):
    pass


@contextfunction
def hide_after_task(context, task_names):
    pass

'''




def get_context(args, state):
    return {
            "solution": args.solution,
            "args": args,
            "state": state,
            "include_task": include_task,
            "include_task_type_replace": include_task_type_replace,
            "include_task_type_append": include_task_type_append,
            "TaskContentType": TaskContentType,
            "ExternalFile": ExternalFile,
            "declare_task_ordering": declare_task_ordering,
            "macros": macros,
            "RecordObject": RecordObject,
            "write_manifest": write_manifest,
            "capdl_my_cspace": capdl_my_cspace,
            "capdl_my_vspace": capdl_my_vspace,
            "capdl_empty_slot": capdl_empty_slot,

            # capDL objects
            'seL4_EndpointObject':seL4_EndpointObject,
            'seL4_NotificationObject':seL4_NotificationObject,
            'seL4_TCBObject':seL4_TCBObject,
            'seL4_ARM_SmallPageObject':seL4_ARM_SmallPageObject,
            'seL4_ARM_SectionObject':seL4_ARM_SectionObject,
            'seL4_ARM_SuperSectionObject':seL4_ARM_SuperSectionObject,
            'seL4_FrameObject':seL4_FrameObject,
            'seL4_UntypedObject':seL4_UntypedObject,
            'seL4_IA32_IOPort':seL4_IA32_IOPort,
            'seL4_IA32_IOSpace':seL4_IA32_IOSpace,
            'seL4_ARM_IOSpace':seL4_ARM_IOSpace,
            'seL4_SchedContextObject':seL4_SchedContextObject,
            'seL4_SchedControl':seL4_SchedControl,
            'seL4_RTReplyObject':seL4_RTReplyObject,
            'seL4_ASID_Pool':seL4_ASID_Pool,
            'seL4_CanRead':seL4_CanRead,
            'seL4_CanWrite':seL4_CanWrite,
            'seL4_AllRights':seL4_AllRights,
            'seL4_IRQControl':seL4_IRQControl,

    }


def get_filters():
    return {
        'File': File,
        'TaskContent': TaskContent,
        'TaskCompletion': TaskCompletion,
        'ExcludeDocs': ExcludeDocs,
        'ELF': ELF,
    }


